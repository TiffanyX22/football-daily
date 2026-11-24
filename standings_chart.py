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
            image = Image.new('RGB', (WIDTH, 1312), BG)
            draw = ImageDraw.Draw(image)
            draw.text((48, 35), league + ' · 积分榜 / TABLE', fill=ACCENT, font=font(39))
            draw.text((48, 102), report['day'] + ' · ' + group['name'], fill=FG, font=font(24))
            updated = dt.datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%m-%d %H:%M')
            draw.text((48, 152), '更新 / Updated ' + updated + ' LA · 浅绿为本期参赛球队', fill=MUTED, font=font(21))
            missing_names = [r['team'] for r in rows if not r['team_zh']]
            missing_logos = []
            if missing_names:
                report['errors'].append(league + '：缺少中文队名：' + ', '.join(missing_names))
            columns = 2 if len(rows) > 18 else 1
            per_column = (len(rows) + columns - 1) // columns
            row_h = min(56, 970 // max(1, per_column))
            if row_h < 42:
                raise RuntimeError('Standings cannot fit legibly on one portrait card')
            for column in range(columns):
                x = 48 + column * 500
                for offset, title in [(0,'#'), (75,'球队 / TEAM'), (345,'场'), (390,'净'), (448,'分')]:
                    draw.text((x + offset, 216), title, fill=ACCENT, font=font(18))
                for index, row in enumerate(rows[column*per_column:(column+1)*per_column]):
                    y = 255 + index*row_h
                    if row['team'] in played:
                        draw.rounded_rectangle((x-7,y-3,x+477,y+row_h-5),radius=6,fill='#2b4032')
                    draw.text((x,y+12),row['rank'],font=font(20),fill=FG)
                    if row['logo']:
                        try:
                            data,_=fetch(row['logo'],binary=True)
                            crest=ImageOps.contain(Image.open(io.BytesIO(data)).convert('RGBA'),(32,32))
                            image.paste(crest,(x+34,y+8),crest)
                        except Exception:
                            missing_logos.append(row['team'])
                    else:
                        missing_logos.append(row['team'])
                    for value,top,size,color in [(row['team_zh'] or row['team'],y,21,FG),(row['team'],y+29,13,MUTED)]:
                        while font(size).getlength(value)>258 and size>10:
                            size-=1
                        draw.text((x+75,top),value,font=font(size),fill=color)
                    for offset,value in [(345,row.get('gamesPlayed','—')),(390,row.get('pointDifferential','—')),(448,row['points'])]:
                        draw.text((x+offset,y+12),value,font=font(20),fill=ACCENT if offset==448 else FG)
            if missing_logos:
                report['errors'].append(league+'：队标加载失败：'+', '.join(missing_logos))
            draw.text((48,1240),'场 / GP · 净 / GD · 分 / PTS · 各队场次可能不同',font=font(20),fill=MUTED)
            draw.text((48,1275),'来源：ESPN · 抓取时快照 / Current snapshot',font=font(18),fill=MUTED)
            path=folder/f'standings-{slug}-{group_index}-zh-en-crests-social.png'
            image.save(path,'PNG',optimize=True)
            assets.append({'url':prefix+'/'+path.name,'filename':path.name,'league':league,
                           'group':group['name'],'source':source,'rows':rows,
                           'bilingual_complete':not missing_names,'logos_complete':not missing_logos})
    report['standings_charts'] = assets
    return [folder / a['filename'] for a in assets]
