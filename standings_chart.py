"""Point-table snapshots from ESPN, exported as social PNGs."""
import json
import datetime as dt
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
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
            rows.append({'team': entry['team']['displayName'], **stats})
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
            height = 420 + len(rows) * 74 + 170
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
            y = 410
            for row in rows:
                active = row['team'] in played
                if active:
                    draw.rounded_rectangle((PAD - 12, y - 6, WIDTH - PAD + 20, y + 60), radius=8, fill='#2b4032')
                values = [row['rank'], row['team'], row.get('gamesPlayed', '—'), row.get('pointDifferential', '—'), row['points'], '●' if active else '']
                for col, (x, value) in enumerate(zip(xs, values)):
                    size = 27
                    if col == 1:
                        while font(size).getlength(value) > 495 and size > 17:
                            size -= 1
                    draw.text((x, y), value, fill=ACCENT if col == 4 else FG, font=font(size))
                y += 74
            draw.text((PAD, y + 20), '来源：ESPN · 抓取时积分快照', fill=MUTED, font=font(25))
            draw.text((PAD, y + 65), '非赛前后名次变化；晋级以赛事官方最终规则及结果为准。', fill=MUTED, font=font(22))
            path = folder / f'standings-{slug}-{group_index}.png'
            image.save(path, 'PNG', optimize=True)
            assets.append({'url': prefix + '/' + path.name, 'filename': path.name, 'league': league,
                           'group': group['name'], 'source': source, 'rows': rows})
    report['standings_charts'] = assets
    return [folder / a['filename'] for a in assets]
