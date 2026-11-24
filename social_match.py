"""A complete match report on one fixed-size portrait card."""
import io
from PIL import Image, ImageDraw, ImageOps
import qrcode
from poster import WIDTH, BG, FG, MUTED, ACCENT, font, TEAM_NAMES, translated
from players import label, show_assist


def draw_match(match, day, path, fetch, public_base):
    image = Image.new('RGB', (WIDTH, 1312), BG)
    draw = ImageDraw.Draw(image)
    def text(value, x, y, size=24, color=FG, width=940):
        while font(size).getlength(value) > width and size > 10:
            size -= 1
        draw.text((x, y), value, font=font(size), fill=color)
    text(day + ' · ' + match['league'] + ' / FULL TIME', 52, 24, 25, ACCENT)
    crests = 0
    for side, x in [('home', 52), ('away', 642)]:
        name = match[side]
        url = match.get('team_logos', {}).get(name, '')
        if url:
            try:
                data, _ = fetch(url, binary=True)
                crest = ImageOps.contain(Image.open(io.BytesIO(data)).convert('RGBA'), (70, 70))
                image.paste(crest, (x, 79), crest)
                crests += 1
            except Exception:
                pass
        text(TEAM_NAMES.get(name, name), x + 87, 76, 34, FG, 296)
        text(name, x + 87, 125, 20, MUTED, 296)
    text(match['score'], 452, 85, 55, ACCENT, 160)
    text('洛杉矶开球 / LA kickoff ' + match['kickoff'][:16].replace('T', ' '), 52, 181, 21, MUTED)
    embedded = False
    credit = '现场照片暂缺 / Match photo unavailable'
    for photo in match['photos']:
        try:
            data, mime = fetch(photo['url'], binary=True)
            if not mime.startswith('image/'):
                continue
            photo_image = ImageOps.contain(Image.open(io.BytesIO(data)).convert('RGB'), (976, 285))
            image.paste(photo_image, ((WIDTH - photo_image.width)//2, 225 + (285 - photo_image.height)//2))
            credit = photo.get('credit', '') + ' · 本场比赛 / Match photo'
            embedded = True
            break
        except Exception:
            continue
    text(credit, 52, 518, 17, MUTED, 976)
    draw.line((52, 554, 1028, 554), fill='#3c5145', width=2)
    text('关键时刻 / KEY MOMENTS', 52, 570, 27, ACCENT)
    events = match['timeline']
    # Space is reserved for standings, the QR, sources, and all events.
    row_h = min(94, 418 // max(1, len(events)))
    y = 620
    kinds = {'Goal': '进球', 'Penalty - Scored': '点球命中', 'Goal - Free-kick': '任意球进球',
             'Goal - Header': '头球进球', 'Goal - Volley': '凌空进球', 'Own Goal': '乌龙球',
             'Red Card': '红牌', 'Yellow Red Card': '两黄变红'}
    for event in events:
        player = event.get('player')
        who = label(player) if player else event['players']
        text(event['minute'] + ' ' + kinds.get(event['type'], event['type']) + ' · ' + who,
             52, y, min(27, max(18, row_h // 3)), FG, 976)
        if show_assist(event):
            assist = label(event['assist']) if event.get('assist') else '数据源未记录 / Not recorded'
            text('助攻 / Assist：' + assist, 76, y + min(37, row_h//2), min(22, max(15, row_h//3-2)), MUTED, 950)
        y += row_h
    if not events:
        text('关键事件资料暂缺 / Event details unavailable', 52, y, 24, MUTED)
    draw.line((52, 1054, 1028, 1054), fill='#3c5145', width=2)
    text('积分与排名 / POINTS & RANK', 52, 1066, 25, ACCENT)
    for index, row in enumerate(match.get('standings', [])[:2]):
        text(translated(row), 52, 1110 + index * 34, 21, FG, 976)
    if not match.get('standings'):
        text(translated(match['impact']), 52, 1110, 21, FG, 976)
    target = match['highlights'][0]['url'] if match['highlights'] else public_base + '/reports/' + day + '.html#' + match['id']
    qr = qrcode.make(target).convert('RGB').resize((112,112),Image.Resampling.NEAREST)
    image.paste(qr,(916,1184))
    text('扫码看官方集锦 / Official highlights' if match['highlights'] else '扫码看完整战报 / Full report',52,1190,22,ACCENT,835)
    text('积分为抓取时快照 · 图源版权归原作者',52,1232,18,MUTED,835)
    text('tiffanyx22.github.io/football-daily',52,1265,18,MUTED,835)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path,'PNG',optimize=True)
    return {'width':1080,'height':1312,'image_embedded':embedded,'team_crests_embedded':crests}
