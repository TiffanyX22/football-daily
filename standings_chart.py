"""Point-table snapshots from ESPN, exported as social PNGs."""
import json
import io
from pathlib import Path
import datetime as dt
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageOps
from poster import WIDTH, PAD, BG, FG, MUTED, ACCENT, font


def tables(payload):
    result = []
    def visit(node):
        table = node.get('standings', {})
        rows = []
        for entry in table.get('entries', []):
            stats = {s['name']: s.get('displayValue', str(s.get('value', ''))) for s in entry.get('stats', [])}
            if not stats.get('points') or not stats.get('rank'):
                continue
            team = entry['team']
            names = json.loads(Path(__file__).with_name('team-names.json').read_text())
            name = team['displayName']
            rows.append({'team': name, 'team_zh': names.get(name, ''),
                         'logo': next((x['href'] for x in team.get('logos', []) if x.get('href', '').startswith('https://')), ''), **stats})
        if rows:
            rows.sort(key=lambda r: float(r['rank']))
            result.append({'name': node.get('name', ''), 'rows': rows})
        for child in node.get('children', []):
            visit(child)
    visit(payload)
    return result


def export_tables(report, out, fetch, prefix, folder):
    assets = []
    for slug, league in sorted({(m['slug'], m['league']) for m in report['matches']}):
        source = f'https://site.web.api.espn.com/apis/v2/sports/soccer/{slug}/standings'
        try:
            groups = tables(json.loads(fetch(source)))
        except Exception:
            report['errors'].append(f'{league}：积分表抓取失败，未生成积分图')
            continue
        played = {m[k] for m in report['matches'] if m['slug'] == slug for k in ('home', 'away')}
        for group_index, group in enumerate(groups, 1):
            rows = group['rows']
            height = 420 + len(rows) * 102 + 170
            image = Image.new('RGB', (WIDTH, height), BG)
            draw = ImageDraw.Draw(image)
            draw.text((PAD, 44), 'TABLE / 积分榜', fill=ACCENT, font=font(30))
            draw.text((PAD, 108), league + ' · ' + report['day'], fill=FG, font=font(48))
            draw.text((PAD, 188), group['name'], fill=MUTED, font=font(28))
            draw.text((PAD, 240), '更新：' + dt.datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d %H:%M') + ' 洛杉矶', fill=MUTED, font=font(25))
            draw.text((PAD, 287), '浅绿标出本期参赛球队 · 各队已赛场次可能不同', fill=MUTED, font=font(24))
            xs = [PAD, 145, 665, 765, 870, 960]
            for x, label in zip(xs, ['名次', '球队', '场次', '净胜', '积分', '本期']):
                draw.text((x, 350), label, fill=ACCENT, font=font(24))
            missing_names = [r['team'] for r in rows if not r['team_zh']]
            if missing_names:
                report['errors'].append(league + '：缺少中文队名：' + ', '.join(missing_names))
            y = 410
            missing_logos = []
            for row in rows:
                active = row['team'] in played
                if active:
                    draw.rounded_rectangle((PAD - 12, y - 6, WIDTH - PAD + 20, y + 88), radius=8, fill='#2b4032')
                if row['logo']:
                    try:
                        data, mime = fetch(row['logo'], binary=True)
                        logo = Image.open(io.BytesIO(data)).convert('RGBA')
                        logo = ImageOps.contain(logo, (62, 62))
                        image.paste(logo, (140 + (62 - logo.width) // 2, y + 8), logo)
                    except Exception:
                        missing_logos.append(row['team'])
                else:
                    missing_logos.append(row['team'])
                for value, top, size, color in [(row['team_zh'] or row['team'], y, 29, FG), (row['team'], y + 45, 20, MUTED)]:
                    while font(size).getlength(value) > 425 and size > 12:
                        size -= 1
                    draw.text((220, top), value, fill=color, font=font(size))
                values = [row['rank'], row.get('gamesPlayed', '—'), row.get('pointDifferential', '—'), row['points'], '●' if active else '']
                for x, value in zip([PAD, 665, 765, 870, 960], values):
                    draw.text((x, y + 21), value, fill=ACCENT if x == 870 else FG, font=font(27))
                y += 102
            if missing_logos:
                report['errors'].append(league + '：队标加载失败：' + ', '.join(missing_logos))
            draw.text((PAD, y + 20), '来源：ESPN · 抓取时积分快照', fill=MUTED, font=font(25))
            draw.text((PAD, y + 65), '非赛前后名次变化；晋级以赛事官方最终规则及结果为准。', fill=MUTED, font=font(22))
            path = folder / f'standings-{slug}-{group_index}-zh-en-crests.png'
            image.save(path, 'PNG', optimize=True)
            assets.append({'url': prefix + '/' + path.name, 'filename': path.name, 'league': league,
                           'group': group['name'], 'source': source, 'rows': rows,
                           'bilingual_complete': not missing_names, 'logos_complete': not missing_logos})
    report['standings_charts'] = assets
    return [folder / a['filename'] for a in assets]
