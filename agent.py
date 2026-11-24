"""Daily men's football digest. Python standard library only; no paid APIs."""
import argparse
import concurrent.futures
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

LA = ZoneInfo('America/Los_Angeles')
UTC = dt.timezone.utc
BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer/'
LEAGUES = {
    'eng.1': '英超', 'esp.1': '西甲', 'fra.1': '法甲', 'ita.1': '意甲',
    'ger.1': '德甲', 'uefa.champions': '欧冠', 'fifa.world': '世界杯',
    'fifa.worldq.uefa': '世预赛欧洲', 'fifa.worldq.conmebol': '世预赛南美',
    'fifa.worldq.concacaf': '世预赛中北美', 'fifa.worldq.afc': '世预赛亚洲',
    'fifa.worldq.caf': '世预赛非洲', 'fifa.worldq.ofc': '世预赛大洋洲',
    'uefa.euro': '欧洲杯', 'uefa.nations': '欧国联',
    'conmebol.america': '美洲杯', 'concacaf.gold': '金杯赛',
    'concacaf.nations.league': '中北美国联', 'caf.nations': '非洲杯',
    'afc.asian.cup': '亚洲杯', 'fifa.confederations': '联合会杯',
    'fifa.friendly': '成年男足友谊赛',
}
LEAGUE_DOMAINS = {'eng.1': ['premierleague.com'], 'esp.1': ['laliga.com'],
                  'ita.1': ['legaseriea.it'], 'ger.1': ['bundesliga.com'],
                  'fra.1': ['ligue1.com'], 'uefa.champions': ['uefa.com']}


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta':
            self.meta[a.get('property', a.get('name', ''))] = a.get('content', '')


def curated_assets(event_id, home, away):
    """Reviewed exact-event URLs are supplemental, never a substitute for discovery."""
    path = Path(__file__).with_name('reviewed-media.json')
    item = json.loads(path.read_text()).get(str(event_id), {}) if path.exists() else {}
    images, videos = [], []
    for page in item.get('pages', []):
        try:
            body = fetch(page['url'])
            meta = MetaParser()
            meta.feed(body)
            if page['date'] not in body:
                continue
            image = meta.meta.get('og:image', '')
            if image.startswith('https://'):
                _, mime = fetch(image, binary=True)
                if mime.startswith('image/'):
                    images.append({'url': image, 'caption': page['caption'],
                                   'credit': page['publisher'], 'source': page['url']})
            if page.get('video') and re.search(r'VideoObject|<video|<iframe|videoId|video-js|brightcove', body, re.I):
                videos.append({'url': page['url'], 'title': page['caption'], 'publisher': page['publisher']})
        except Exception:
            continue
    return images, videos


def normalized(name):
    import unicodedata
    name = ''.join(c for c in unicodedata.normalize('NFKD', name.lower()) if not unicodedata.combining(c))
    aliases = {'man utd': 'manchester united', 'man city': 'manchester city', 'milan': 'ac milan',
               'atl madrid': 'atletico madrid', 'w bremen': 'werder bremen', 'sociedad': 'real sociedad',
               'racing': 'racing santander', 'paris fc': 'paris fc', 'le mans': 'le mans'}
    name = aliases.get(name, name)
    return re.sub(r'[^a-z0-9]', '', name)


def reconcile(day, matches, leagues):
    """Independent daily score count audit for the five domestic leagues.

    Soccerbase uses UK calendar dates; only compare when its entire UK date
    lies inside the LA reporting window (true for normal European evenings).
    Cups/nationals remain explicitly primary-provider only.
    """
    url = 'https://www.soccerbase.com/matches/results.sd?date=' + str(day)
    body = fetch(url)
    competition_map = {'Premier League': 'eng.1', 'Italian Serie A': 'ita.1',
                       'German Bundesliga': 'ger.1', 'Spanish La Liga': 'esp.1', 'French Ligue 1': 'fra.1'}
    current, expected = None, []
    for row in re.findall(r'<tr\b[^>]*>.*?</tr>', body, re.S | re.I):
        heading = re.search(r'<h2[^>]*>.*?</h2>', row, re.S)
        if heading:
            name = html.unescape(re.sub('<[^>]+>', '', heading.group()))
            current = competition_map.get(name)
        if not current or current not in leagues or 'homeTeam' not in row or 'class="finished"' not in row:
            continue
        def cell(kind):
            match = re.search(r'<td[^>]*class="[^"]*' + kind + r'[^\"]*"[^>]*>(.*?)</td>', row, re.S)
            return html.unescape(re.sub('<[^>]+>', '', match.group(1))).strip() if match else ''
        home, away = cell('homeTeam'), cell('awayTeam')
        score = re.findall(r'<em>(\d+)</em>', row)
        if home and away and len(score) == 2:
            expected.append((current, home, away, '–'.join(score)))
    findings = []
    for slug, home, away, score in expected:
        found = next((m for m in matches if m['slug'] == slug and normalized(m['home']) == normalized(home)
                      and normalized(m['away']) == normalized(away)), None)
        if not found:
            findings.append(f'独立赛果源有记录但主清单未匹配：{home} {score} {away}（可能漏报或队名别名缺失）')
        elif found['score'] != score:
            findings.append(f'比分冲突：{home} vs {away}')
    return {'url': url, 'expected': len(expected), 'findings': findings,
            'scope': '五大联赛当日UK赛果单向交叉核对；跨日及国家队/欧冠仍以主源为准'}


def fetch(url, binary=False):
    if not url.startswith('https://'):
        raise ValueError('Only HTTPS sources allowed')
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'FootballDigest/1.0 (personal noncommercial digest)'})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read(4_000_000)
                if binary:
                    return data, r.headers.get('Content-Type', '')
                return data.decode('utf-8', errors='replace')
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def get_json(url):
    return json.loads(fetch(url))


def instant(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def window(day):
    end = dt.datetime.combine(day, dt.time(16), LA)
    # Calendar-day arithmetic preserves 16:00 over DST transitions.
    start = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(16), LA)
    return start, end


def final_time(summary):
    events = summary.get('keyEvents', [])
    endings = [e for e in events if e.get('type', {}).get('type') in
               ('end-regular-time', 'end-extra-time', 'end-shootout', 'end-match') and e.get('wallclock')]
    return max((instant(e['wallclock']) for e in endings), default=None)


def source_url(event):
    return next((x['href'] for x in event.get('links', [])
                 if 'summary' in x.get('rel', [])),
                'https://www.espn.com/soccer/match/_/gameId/' + event['id'])


def collect(day, leagues=None):
    start, end = window(day)
    # Include overlapping UTC dates plus a prior day for long/delayed fixtures.
    dates = [(start.astimezone(UTC).date() + dt.timedelta(days=n)).strftime('%Y%m%d')
             for n in (-1, 0, 1)]
    events, errors, scans = {}, [], []

    def scan(slug, date):
        url = BASE + slug + '/scoreboard?' + urllib.parse.urlencode({'dates': date, 'limit': 1000})
        d = get_json(url)
        if 'events' not in d:
            raise ValueError('No events field in scoreboard')
        if len(d['events']) >= 1000:
            raise ValueError('Possible truncated scoreboard')
        return slug, date, d['events']

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        tasks = {pool.submit(scan, slug, date): (slug, date)
                 for slug in (leagues or LEAGUES) for date in dates}
        for task in concurrent.futures.as_completed(tasks):
            slug, date = tasks[task]
            try:
                _, _, found = task.result()
                scans.append({'league': slug, 'date': date, 'count': len(found)})
                for event in found:
                    kickoff = instant(event['date'])
                    if start - dt.timedelta(hours=8) <= kickoff < end:
                        events[(slug, event['id'])] = event
            except Exception as e:
                errors.append(f'{slug} {date}: {type(e).__name__}: {e}')
    return events, errors, scans


def valid_photo(image):
    url = image.get('url', '')
    if not url.startswith('https://') or '/photo/' not in url:
        return False
    if image.get('width', 0) < 600 or image.get('height', 0) < 300:
        return False
    try:
        _, content_type = fetch(url, binary=True)
        return content_type.startswith('image/')
    except Exception:
        return False


def photos(summary, event_id):
    # Only the recap explicitly tied to this event. League-wide news often
    # contains unrelated transfer images and must NEVER supply match photos.
    article = summary.get('article') or {}
    if str(article.get('gameId', '')) != str(event_id) or article.get('type') != 'Recap':
        return []
    result = []
    for image in article.get('images', []):
        if valid_photo(image):
            result.append({'url': image['url'], 'caption': image.get('alt') or image.get('name', ''),
                           'credit': image.get('credit', ''),
                           'source': f'https://www.espn.com/soccer/report/_/gameId/{event_id}'})
        if len(result) == 2:
            break
    return result


def official_highlights(home, away, day, rules, slug):
    """Search discovered URLs, never fabricate paths. Verify publisher and metadata.

    Allowlisted publishers are configured in publishers.json. No search URL is
    presented as a video. When discovery is blocked, return explicit missing data.
    """
    domains = list(dict.fromkeys(rules.get(home, []) + rules.get(away, []) + LEAGUE_DOMAINS.get(slug, [])))
    matches = []
    for domain in domains[:3]:
        query = f'site:{domain} "{home}" "{away}" {day.isoformat()} highlights resumen'
        url = 'https://www.bing.com/search?' + urllib.parse.urlencode({'q': query, 'format': 'rss'})
        try:
            root = ET.fromstring(fetch(url))
            for item in root.findall('.//item')[:4]:
                link = item.findtext('link', '')
                host = urllib.parse.urlparse(link).hostname or ''
                if not (host == domain or host.endswith('.' + domain)):
                    continue
                body = fetch(link)
                title = re.search(r'<title[^>]*>(.*?)</title>', body, re.S | re.I)
                title = html.unescape(re.sub('<[^>]+>', '', title.group(1))) if title else ''
                if not all(name.casefold() in title.casefold() for name in (home, away)):
                    continue
                if not re.search(r'highlights|resumen|sintesi|集锦', title, re.I):
                    continue
                # Require publication/match date on page as well as video evidence.
                if day.isoformat() not in body or not re.search(r'VideoObject|<video|<iframe|"videoId"', body, re.I):
                    continue
                matches.append({'url': link, 'title': title, 'publisher': domain})
                return matches
        except Exception:
            continue
    return matches


def standings(summary, competitors):
    rows = []
    for group in summary.get('standings', {}).get('groups', []):
        for entry in group.get('standings', {}).get('entries', []):
            stats = {s['name']: s.get('value') for s in entry.get('stats', [])}
            rows.append({'id': str(entry.get('id', '')), 'name': entry.get('team'), **stats})
    result = []
    for team in competitors:
        row = next((r for r in rows if r['id'] == str(team['id'])), None)
        if not row:
            continue
        pts, rank = row.get('points'), row.get('rank')
        text = f"{team['team']['displayName']}：{int(pts)}分，第{int(rank)}名" if pts is not None and rank else '积分名次暂缺'
        if row.get('gamesPlayed') is not None:
            text += f"，已赛{int(row['gamesPlayed'])}场"
        if pts is not None and rows:
            leader = max((r.get('points') or 0 for r in rows))
            text += f"，距本组榜首{int(leader - pts)}分"
        result.append(text + '。')
    return result


def make_match(slug, event, start, end, rules):
    competition = event['competitions'][0]
    if not competition.get('status', {}).get('type', {}).get('completed'):
        return None
    summary = get_json(BASE + slug + '/summary?event=' + event['id'])
    finished = final_time(summary)
    if finished is None:
        # Do not substitute kickoff or guessed end time for confirmed completion.
        raise ValueError('FT但缺少终场时间，无法核实所属窗口：' + event['name'])
    if not (start.astimezone(UTC) <= finished < end.astimezone(UTC)):
        return None
    sides = sorted(competition['competitors'], key=lambda x: x['homeAway'] != 'home')
    home, away = [x['team']['displayName'] for x in sides]
    scores = [str(x['score']) for x in sides]
    timeline = []
    for e in summary.get('keyEvents', []):
        kind = e.get('type', {}).get('type', '')
        if e.get('scoringPlay') or kind in ('red-card', 'yellow-red-card'):
            names = ', '.join(p.get('athlete', {}).get('displayName', '') for p in e.get('participants', []))
            timeline.append({'minute': e.get('clock', {}).get('displayValue', ''),
                             'type': e.get('type', {}).get('text', ''), 'players': names,
                             'text': e.get('text', '')})
    win_points = [1, 1] if scores[0] == scores[1] else ([3, 0] if int(scores[0]) > int(scores[1]) else [0, 3])
    impact = (f'{home}本场获得{win_points[0]}分，{away}获得{win_points[1]}分。'
              if slug in ('eng.1', 'esp.1', 'ita.1', 'ger.1', 'fra.1') else '杯赛晋级影响需按当轮赛制核实，不能套用联赛积分。')
    pictures = photos(summary, event['id'])
    reviewed_images, reviewed_videos = curated_assets(event['id'], home, away)
    pictures = pictures + [p for p in reviewed_images if p['url'] not in {x['url'] for x in pictures}]
    clips = reviewed_videos or official_highlights(home, away, instant(event['date']).astimezone(LA).date(), rules, slug)
    return {'id': event['id'], 'league': LEAGUES[slug], 'slug': slug, 'home': home, 'away': away,
            'score': '–'.join(scores), 'kickoff': instant(event['date']).astimezone(LA).isoformat(),
            'finished': finished.astimezone(LA).isoformat(), 'source': source_url(event),
            'timeline': timeline, 'photos': pictures[:2],
            'highlights': clips,
            'standings': standings(summary, sides), 'impact': impact}


def esc(value):
    return html.escape(str(value), quote=True)


def render(report):
    matches = report['matches']
    photo_count = sum(bool(m['photos']) for m in matches)
    video_count = sum(bool(m['highlights']) for m in matches)
    parts = [f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>男足日报 · {esc(report['day'])}</title><style>
body{{margin:0;background:#101715;color:#edf5ed;font:17px/1.7 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:36px 24px}}a{{color:#a8e5ba}}h1{{font-size:42px;line-height:1.2}}h2{{font-size:30px}}.eyebrow{{color:#a4cc70;letter-spacing:3px}}.muted,figcaption{{color:#a8b8ac;font-size:14px}}article{{border-top:1px solid #405046;padding:36px 0}}figure{{margin:24px 0}}img{{display:block;width:100%;height:auto;border-radius:12px}}.score{{font-size:52px;font-weight:800;color:#d8f59b}}.missing{{padding:12px 16px;background:#302b20;border-radius:8px;color:#edd9aa}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #405046}}nav{{display:flex;gap:12px;flex-wrap:wrap}}.error{{color:#ffc4ae}}li{{margin:8px 0}}
</style><main><p class="eyebrow">FULL TIME / 男足图文日报</p><h1>{esc(report['day'])} 比赛特辑</h1>
<p>{esc(report['start'])} 至 {esc(report['end'])} · 洛杉矶时间 · 按终场时间归档</p>
<p>{len(matches)} 场已核实完赛 · {photo_count} 场有可加载配图（含注明的视频封面） · {video_count} 场找到官方集锦</p>
<p class="muted">自动模板生成，无付费AI。球队名保留数据源原文，避免误译。积分表是抓取时快照，非历史截稿复原；未核实名次升降不作推断。</p>''']
    if report['errors']:
        parts.append('<div class="missing"><b>本期资料不完整，不能声称零漏报。</b><ul>' + ''.join('<li>' + esc(e) + '</li>' for e in report['errors']) + '</ul></div>')
    parts.append('<h2>本期比赛清单</h2><table><tr><th>赛事</th><th>比赛</th><th>比分</th></tr>')
    for m in matches:
        parts.append(f'<tr><td>{esc(m["league"])}</td><td><a href="#{esc(m["id"])}">{esc(m["home"])} — {esc(m["away"])}</a></td><td>{esc(m["score"])}</td></tr>')
    parts.append('</table>')
    if not matches:
        parts.append('<p>此窗口未取得已核实完赛记录。若上方存在数据源错误，这不代表休赛。</p>')
    for m in matches:
        parts.append(f'<article id="{esc(m["id"])}"><p class="eyebrow">{esc(m["league"])}</p><h2>{esc(m["home"])} vs {esc(m["away"])}</h2><div class="score">{esc(m["score"])}</div><p class="muted">开球 {esc(m["kickoff"])} · 终场 {esc(m["finished"])}</p>')
        for p in m['photos']:
            parts.append(f'<figure><img src="{esc(p["url"])}" alt="{esc(p["caption"])}" referrerpolicy="no-referrer" onerror="this.hidden=true;this.nextElementSibling.textContent=\'照片加载失败，请打开来源查看\'"><figcaption>{esc(p["caption"])} · {esc(p["credit"])} · <a href="{esc(p["source"])}">战报照片来源</a></figcaption></figure>')
        if not m['photos']:
            parts.append('<p class="missing">本场暂缺可核实照片；未使用队徽或其他比赛照片替代。</p>')
        parts.append('<h3>关键时刻</h3><ul>')
        for e in m['timeline']:
            parts.append(f'<li><b>{esc(e["minute"])}</b> {esc(e["type"])} · {esc(e["players"])}</li>')
        parts.append('</ul><h3>积分与排名影响</h3><p>' + esc(m['impact']) + '</p>')
        parts.extend('<p>' + esc(s) + '</p>' for s in m['standings'])
        if not m['standings']:
            parts.append('<p class="missing">积分表数据暂缺。</p>')
        parts.append('<nav><a href="' + esc(m['source']) + '">赛果及事件来源</a>')
        for v in m['highlights']:
            parts.append(f'<a href="{esc(v["url"])}">官方集锦 · {esc(v["publisher"])}</a>')
        parts.append('</nav>')
        if not m['highlights']:
            parts.append('<p class="missing">尚未检索核实本场官方集锦；不以搜索页代替。</p>')
        parts.append('</article>')
    parts.append('<footer class="muted">照片版权归原作者，仅嵌入原站公开图片；能加载不代表取得再分发许可。数据源可能缺项或更改接口，详见本期缺项。生成时间 ' + esc(report['generated']) + '</footer></main></html>')
    return ''.join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', help='LA planned reporting day YYYY-MM-DD')
    parser.add_argument('--out', default='docs')
    parser.add_argument('--leagues', help='Comma-separated subset for diagnostics')
    args = parser.parse_args()
    now = dt.datetime.now(LA)
    day = dt.date.fromisoformat(args.date) if args.date else now.date()
    if not args.date and now.hour < 16:
        day -= dt.timedelta(days=1)
    start, end = window(day)
    if end > now:
        parser.error('Cannot generate a future cutoff before 16:00 LA; use a completed reporting day')
    rules = json.loads(Path(__file__).with_name('publishers.json').read_text())
    events, errors, scans = collect(day, args.leagues.split(',') if args.leagues else None)
    matches = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(make_match, slug, event, start, end, rules): event
                   for (slug, _), event in events.items()}
        for future in concurrent.futures.as_completed(futures):
            try:
                match = future.result()
                if match:
                    matches.append(match)
            except Exception as e:
                errors.append(f'{futures[future]["name"]}: {type(e).__name__}: {e}')
    matches.sort(key=lambda m: (m['kickoff'], m['slug'], m['id']))
    ids = [m['id'] for m in matches]
    if len(ids) != len(set(ids)):
        raise RuntimeError('Duplicate event IDs across competitions; publication stopped')
    try:
        audit = reconcile(day, matches, args.leagues.split(',') if args.leagues else LEAGUES)
        errors.extend(audit['findings'])
    except Exception as e:
        audit = {'findings': [str(e)], 'scope': '独立赛果核对失败'}
        errors.append('独立赛果源不可用，无法完成交叉核对')
    report = {'day': str(day), 'start': start.isoformat(), 'end': end.isoformat(),
              'generated': now.isoformat(), 'matches': matches, 'errors': errors,
              'scans': sorted(scans, key=lambda x: (x['league'], x['date'])),
              'audit': audit, 'coverage': audit['scope']}
    out = Path(args.out)
    (out / 'reports').mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    (out / 'reports' / f'{day}.json').write_text(payload)
    page = render(report)
    (out / 'reports' / f'{day}.html').write_text(page)
    (out / 'index.html').write_text(page)
    (out / '.nojekyll').touch()
    print(json.dumps({'date': str(day), 'matches': len(matches),
                      'photos': sum(len(m['photos']) for m in matches),
                      'official_highlights': sum(bool(m['highlights']) for m in matches),
                      'errors': errors}, ensure_ascii=False))
    # Transport/data failure must fail CI, rather than notify a false success.
    return 2 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
