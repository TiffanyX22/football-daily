"""Export one self-contained, downloadable social image per match."""
import io
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
TEAM_NAMES = {'Monza': '蒙扎', 'Fiorentina': '佛罗伦萨', 'Brentford': '布伦特福德',
              'Everton': '埃弗顿', 'Levante': '莱万特', 'Elche': '埃尔切'}


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
    for original, chinese in TEAM_NAMES.items():
        text = text.replace(original, chinese)
    return text


def draw_poster(match, day, output, fetch, public_base):
    # Draw to a generously sized canvas, then crop to actual content height.
    # No text/goal is omitted just to fit an arbitrary social aspect ratio.
    canvas = Image.new('RGB', (WIDTH, 18000), BG)
    draw = ImageDraw.Draw(canvas)
    y = 62

    def text(value, size=30, color=FG, gap=14, x=PAD, width=CONTENT):
        nonlocal y
        face = font(size)
        for line in wrap(value, face, width):
            draw.text((x, y), line, font=face, fill=color)
            y += int(size * 1.55)
        y += gap

    def rule():
        nonlocal y
        y += 14
        draw.line((PAD, y, WIDTH - PAD, y), fill='#3c5145', width=2)
        y += 34

    text('FULL TIME  /  男足比赛特辑', 27, ACCENT, 28)
    text(f"{day}   ·   {match['league']}", 30, MUTED, 28)
    text(TEAM_NAMES.get(match['home'], match['home']), 57, FG, 2)
    text('VS  ' + TEAM_NAMES.get(match['away'], match['away']), 42, MUTED, 18)
    text(match['score'], 150, ACCENT, 6)
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
            selected = ImageOps.contain(original.convert('RGB'), (CONTENT, 630))
            image_credit = photo.get('caption', '') + ' · ' + photo.get('credit', '')
            break
        except Exception:
            continue
    if selected:
        canvas.paste(selected, ((WIDTH - selected.width) // 2, y))
        y += selected.height + 20
    else:
        draw.rounded_rectangle((PAD, y, WIDTH - PAD, y + 180), radius=12, fill='#25392e')
        draw.text((PAD + 30, y + 60), '现场图片暂缺', font=font(38), fill=MUTED)
        y += 205
    text(image_credit, 23, MUTED, 14)
    rule()
    text('关键时刻', 38, ACCENT, 22)
    event_names = {'Goal': '进球', 'Penalty - Scored': '点球命中', 'Goal - Volley': '凌空进球',
                   'Goal - Header': '头球进球', 'Own Goal': '乌龙球', 'Red Card': '红牌',
                   'Yellow Red Card': '两黄变一红'}
    for event in match['timeline']:
        name = event_names.get(event['type'], event['type'])
        text(f"{event['minute']}  {name}  ·  {event['players']}", 30, FG, 18)
    if not match['timeline']:
        text('关键事件资料暂缺，以终场比分为准。', 30, MUTED)
    rule()
    text('积分与排名影响', 38, ACCENT, 22)
    text(translated(match['impact']), 32, FG, 18)
    for row in match['standings']:
        text(translated(row), 29, FG, 14)
    text('积分为抓取时快照；历史补刊不代表当时排名。', 23, MUTED, 10)
    rule()

    target = match['highlights'][0]['url'] if match['highlights'] else f"{public_base}/reports/{day}.html#{match['id']}"
    qr = qrcode.QRCode(box_size=5, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(target)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color='#101b18', back_color='#ffffff').convert('RGB')
    qr_image = qr_image.resize((204, 204), Image.Resampling.NEAREST)
    canvas.paste(qr_image, (WIDTH - PAD - 204, y))
    qr_top = y
    text('扫码看官方集锦' if match['highlights'] else '扫码看完整战报', 32, ACCENT, 12, width=CONTENT - 250)
    text('比分、进球、积分与媒体来源\n见完整日报的来源链接。', 25, MUTED, 8, width=CONTENT - 250)
    y = max(y, qr_top + 226)
    text(public_base.removeprefix('https://'), 25, MUTED, 8)
    text('图源版权归原作者；视频封面已在图注标明。', 22, MUTED, 8)
    y += 42
    if y > canvas.height:
        raise RuntimeError('Poster content exceeds safe canvas height')
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.crop((0, 0, WIDTH, y)).save(output, 'PNG', optimize=True)
    return {'width': WIDTH, 'height': y, 'image_embedded': bool(selected)}


def export(report, out, fetch):
    repository = os.environ.get('GITHUB_REPOSITORY', 'TiffanyX22/football-daily')
    owner, repo = repository.split('/', 1)
    base = os.environ.get('PUBLIC_BASE_URL', f'https://{owner.lower()}.github.io/{repo}').rstrip('/')
    prefix = base + '/posters/' + report['day']
    folder = out / 'posters' / report['day']
    generated = []
    for match in report['matches']:
        path = folder / (match['id'] + '.png')
        metadata = draw_poster(match, report['day'], path, fetch, base)
        match['poster'] = {'url': prefix + '/' + path.name, **metadata}
        generated.append(path)
    if generated:
        bundle = folder / ('football-' + report['day'] + '.zip')
        with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in generated:
                archive.write(path, path.name)
        report['poster_bundle'] = prefix + '/' + bundle.name
