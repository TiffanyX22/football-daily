"""Compact bilingual score covers at a fixed social portrait size."""
import io
import math
from PIL import Image, ImageDraw, ImageOps
from poster import WIDTH, font, TEAM_NAMES

HEIGHT = 1312


def draw_covers(report, folder, fetch, prefix):
    matches = report['matches']
    chunks = [matches[i:i + 9] for i in range(0, len(matches), 9)] or [[]]
    assets = []
    for page, batch in enumerate(chunks, 1):
        image = Image.new('RGB', (WIDTH, HEIGHT))
        draw = ImageDraw.Draw(image)
        for y in range(HEIGHT):
            t = y / HEIGHT
            draw.line((0, y, WIDTH, y), fill=(int(10 - 5*t), int(26 - 16*t), int(135 - 48*t)))
        for k in range(11):
            x = -140 + k * 25
            color = ['#40ebef', '#eef1ff', '#7799ff'][k % 3]
            draw.line((x, HEIGHT, 0, HEIGHT - 230 - k * 14), fill=color, width=3)
            draw.line((WIDTH - x, HEIGHT, WIDTH, HEIGHT - 230 - k * 14), fill=color, width=3)
        title = next(iter({m['league'] for m in matches})) + '赛果' if len({m['league'] for m in matches}) == 1 else '今日男足赛果'
        draw.text((70, 42), title, font=font(68), fill='white')
        draw.text((74, 132), 'DAILY FOOTBALL / FULL-TIME RESULTS', font=font(23), fill='#b4c9ff')
        draw.text((74, 180), report['day'] + ' · 洛杉矶 / Los Angeles', font=font(28), fill='white')
        draw.rounded_rectangle((46, 248, WIDTH - 46, 1208), radius=16, fill='#080e63')
        row_h = 104
        y = 270
        loaded = 0
        for match in batch:
            draw.line((100, y + 95, WIDTH - 100, y + 95), fill='#1c298d', width=1)
            for side, left, right, crest_x in [('home', 80, 389, 406), ('away', 693, 1000, 610)]:
                name = match[side]
                zh = TEAM_NAMES.get(name, name)
                def label(value, top, size, color):
                    while font(size).getlength(value) > right - left and size > 13:
                        size -= 1
                    x = right - font(size).getlength(value) if side == 'home' else left
                    draw.text((x, top), value, font=font(size), fill=color)
                label(zh, y + 11, 31, 'white')
                label(name, y + 55, 17, '#b9c7e8')
                url = match.get('team_logos', {}).get(name, '')
                if url:
                    try:
                        data, _ = fetch(url, binary=True)
                        crest = ImageOps.contain(Image.open(io.BytesIO(data)).convert('RGBA'), (62, 62))
                        image.paste(crest, (crest_x + (62 - crest.width)//2, y + 13 + (62 - crest.height)//2), crest)
                        loaded += 1
                    except Exception:
                        pass
            score = match['score'].replace('–', '-')
            draw.text(((WIDTH - font(36).getlength(score))/2, y + 22), score, font=font(36), fill='#46f5eb')
            if len({m['league'] for m in matches}) > 1:
                draw.text(((WIDTH - font(15).getlength(match['league']))/2, y + 70), match['league'], font=font(15), fill='#b9c7e8')
            y += row_h
        if not batch:
            draw.text((180, 500), '本期无已核实完赛 / No completed matches', font=font(26), fill='white')
        caption = f"{len(matches)}场 / matches · {page}/{len(chunks)} · LA " + report['end'][11:16]
        draw.text((74, 1240), caption, font=font(23), fill='#c5d6ff')
        path = folder / f"cover-{report['day']}-social-{page}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, 'PNG', optimize=True)
        assets.append({'filename': path.name, 'url': prefix + '/' + path.name, 'matches': len(batch), 'team_crests_embedded': loaded})
    return assets
