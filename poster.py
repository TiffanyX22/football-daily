"""Export one self-contained, downloadable social image per match."""
import io
import json
import os
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode

WIDTH = 1080
PAD = 64
CONTENT = WIDTH - PAD * 2
BG = '#101b18'
FG = '#f2f5ec'
MUTED = '#b0c1b4'
ACCENT = '#d5f48f'
TEAM_NAMES = json.loads(Path(__file__).with_name('team-names.json').read_text())


def font(size):
    candidates = [os.environ.get('POSTER_FONT', ''),
                  '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                  '/System/Library/Fonts/Hiragino Sans GB.ttc',
                  '/System/Library/Fonts/Supplemental/Arial Unicode.ttf']
    path = next((p for p in candidates if p and Path(p).exists()), None)
    if not path:
        raise RuntimeError('Chinese font required. Install fonts-noto-cjk or set POSTER_FONT.')
    return ImageFont.truetype(path, size)


def wrap(text, face, max_width=CONTENT):
    lines, line = [], ''
    for character in str(text):
        if character == '\n':
            lines.append(line)
            line = ''
        elif line and face.getlength(line + character) > max_width:
            lines.append(line)
            line = character
        else:
            line += character
    if line:
        lines.append(line)
    return lines


def translated(text):
    for original, chinese in sorted(TEAM_NAMES.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(original, chinese)
    return text


def draw_poster(match, day, output, fetch, public_base):
    # Draw to a generously sized canvas, then crop to actual content height.
    # No text/goal is omitted just to fit an arbitrary social aspect ratio.
    canvas = Image.new('RGB', (WIDTH, 18000), BG)
    draw = ImageDraw.Draw(canvas)
    y = 62
    breaks = [0]

    def text(value, size=30, color=FG, gap=14, x=PAD, width=CONTENT):
        nonlocal y
        face = font(size)
        for line in wrap(value, face, width):
            draw.text((x, y), line, font=face, fill=color)
            y += int(size * 1.55)
        y += gap
        if color != ACCENT:
            breaks.append(y)

    def rule():
        nonlocal y
        y += 14
        draw.line((PAD, y, WIDTH - PAD, y), fill='#3c5145', width=2)
        y += 34

    text('FULL TIME  /  男足比赛特辑', 27, ACCENT, 28)
    text(f"{day}   ·   {match['league']}", 30, MUTED, 28)
    loaded_crests = []
    def team_heading(name, versus=False):
        top = y
        url = match.get('team_logos', {}).get(name, '')
        if url:
            try:
                data, mime = fetch(url, binary=True)
                crest = ImageOps.contain(Image.open(io.BytesIO(data)).convert('RGBA'), (104, 104))
                canvas.paste(crest, (PAD + (104 - crest.width) // 2, top + (104 - crest.height) // 2), crest)
                loaded_crests.append(name)
            except Exception:
                pass
        text(('VS  ' if versus else '') + TEAM_NAMES.get(name, name), 48, FG, 2, x=PAD + 130, width=CONTENT - 130)
        text(name, 27, MUTED, 18, x=PAD + 130, width=CONTENT - 130)
    team_heading(match['home'])
    team_heading(match['away'], versus=True)
    text(match['score'], 100, ACCENT, 6)
    text('洛杉矶开球时间 ' + match['kickoff'][:16].replace('T', ' '), 26, MUTED, 24)

    image_credit = '本场无可核实图片，未使用其他比赛照片替代。'
    selected = None
    for photo in match['photos']:
        try:
            data, mime = fetch(photo['url'], binary=True)
            if not mime.startswith('image/'):
                continue
            original = Image.open(io.BytesIO(data))
            original.load()
            selected = ImageOps.contain(original.convert('RGB'), (CONTENT, 400))
            image_credit = photo.get('caption', '') + ' · ' + photo.get('credit', '')
            break
        except Exception:
            continue
    if selected:
        breaks.append(y)
        canvas.paste(selected, ((WIDTH - selected.width) // 2, y))
        y += selected.height + 20
        breaks.append(y)
    else:
        draw.rounded_rectangle((PAD, y, WIDTH - PAD, y + 180), radius=12, fill='#25392e')
        draw.text((PAD + 30, y + 60), '现场图片暂缺', font=font(38), fill=MUTED)
        y += 205
    text(image_credit, 23, MUTED, 14)
    rule()
    text('关键时刻', 38, ACCENT, 22)
    event_names = {'Goal': '进球', 'Penalty - Scored': '点球命中', 'Goal - Volley': '凌空进球',
                   'Goal - Header': '头球进球', 'Goal - Free-kick': '任意球进球', 'Own Goal': '乌龙球', 'Red Card': '红牌',
                   'Yellow Red Card': '两黄变一红'}
    for event in match['timeline']:
        name = event_names.get(event['type'], event['type'])
        from players import label, show_assist
        text(f"{event['minute']}  {name}  ·  " + (label(event['player']) if event.get('player') else event['players']), 30, FG, 10)
        if show_assist(event):
            text('助攻：' + (label(event['assist']) if event.get('assist') else '数据源未记录'), 27, MUTED, 20)
    if not match['timeline']:
        text('关键事件资料暂缺，以终场比分为准。', 30, MUTED)
    rule()
    text('积分与排名影响', 38, ACCENT, 22)
    text(translated(match['impact']), 32, FG, 18)
    for row in match['standings']:
        text(translated(row), 29, FG, 14)
    text('积分为抓取时快照；历史补刊不代表当时排名。', 23, MUTED, 10)
    rule()

    y = breaks[-1] + 12
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.crop((0, 0, WIDTH, y)).save(output, 'PNG', optimize=True)
    return {'width': WIDTH, 'height': y, 'image_embedded': bool(selected), 'team_crests_embedded': len(loaded_crests), '_breaks': breaks}


def paginate(path, breaks, title, target=None):
    original = Image.open(path).convert('RGB')
    body = 1110
    positions = sorted(set([0, *breaks, original.height]))
    pages, start = [], 0
    while start < original.height:
        candidates = [p for p in positions if start < p <= start + body]
        if not candidates:
            raise RuntimeError('Image block cannot fit fixed portrait page')
        end = max(candidates)
        # Never cut photographs, QR codes, or text at an arbitrary pixel row.
        page = Image.new('RGB', (WIDTH, 1312), BG)
        d = ImageDraw.Draw(page)
        heading = title
        size = 23
        while font(size).getlength(heading) > CONTENT and size > 12:
            size -= 1
        d.text((PAD, 15), heading, font=font(size), fill=MUTED)
        page.paste(original.crop((0, start, WIDTH, end)), (0, 62))
        output = path.with_name(path.stem + '-social-' + str(len(pages) + 1) + '.png')
        d.text((PAD, 1210), f'比赛特辑 / MATCH REPORT · {len(pages) + 1}', font=font(22), fill=ACCENT)
        if target:
            qr = qrcode.make(target).convert('RGB').resize((114, 114), Image.Resampling.NEAREST)
            page.paste(qr, (WIDTH - PAD - 114, 1188))
            d.text((PAD, 1250), '扫码看官方集锦 / Official highlights', font=font(21), fill=MUTED)
        page.save(output, 'PNG', optimize=True)
        pages.append(output)
        start = end
    path.unlink()
    return pages


def export(report, out, fetch):
    repository = os.environ.get('GITHUB_REPOSITORY', 'TiffanyX22/football-daily')
    owner, repo = repository.split('/', 1)
    base = os.environ.get('PUBLIC_BASE_URL', f'https://{owner.lower()}.github.io/{repo}').rstrip('/')
    prefix = base + '/posters/' + report['day']
    folder = out / 'posters' / report['day']
    from cover import draw_covers
    report['covers'] = draw_covers(report, folder, fetch, prefix)
    report['cover'] = report['covers'][0]
    generated = [folder / a['filename'] for a in report['covers']]
    for match in report['matches']:
        path = folder / (match['id'] + '-zh-en.png')
        from social_match import draw_match
        metadata = draw_match(match, report['day'], path, fetch, base)
        match['poster_pages'] = [{'filename': path.name, 'url': prefix + '/' + path.name}]
        match['poster'] = {**match['poster_pages'][0], **metadata}
        generated.append(path)
    from standings_chart import export_tables
    generated.extend(export_tables(report, out, fetch, prefix, folder))
    if generated:
        bundle = folder / ('football-' + report['day'] + '-social.zip')
        with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in generated:
                archive.write(path, path.name)
        report['poster_bundle'] = prefix + '/' + bundle.name
