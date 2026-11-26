"""Send report posters and ZIP directly by Gmail SMTP; credentials stay in Secrets."""
import argparse
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import html
import io
import json
import os
from pathlib import Path
import smtplib
import ssl
import zipfile

from PIL import Image

MAX_GROUP_BYTES = 6 * 1024 * 1024
MAX_EMAIL_BYTES = 22 * 1024 * 1024


def groups(paths):
    batches, current, size = [], [], 0
    for path in paths:
        length = path.stat().st_size
        if length > MAX_GROUP_BYTES:
            raise ValueError('A single poster exceeds the attachment size limit')
        if current and size + length > MAX_GROUP_BYTES:
            batches.append(current)
            current, size = [], 0
        current.append(path)
        size += length
    if current:
        batches.append(current)
    return batches


def build_messages(report, folder, sender, recipient):
    from daily_delivery import missing_media
    missing = missing_media(report)
    media_notice = '\n'.join(f"{m['home']} vs {m['away']}：{'、'.join(missing[str(m['id'])])}"
                             for m in report['matches'] if str(m['id']) in missing)
    day = report['day']
    root = folder / 'posters' / day
    paths = [root / page['filename'] for m in report['matches'] for page in m.get('poster_pages', [m.get('poster', {'filename': m['id'] + '.png'})])]
    covers = report.get('covers', [report['cover']] if report.get('cover') else [])
    paths = [root / c['filename'] for c in covers] + paths
    paths += [root / chart['filename'] for chart in report.get('standings_charts', [])]
    batches = groups(paths) or [[]]
    messages = []
    for index, batch in enumerate(batches, 1):
        msg = EmailMessage()
        msg['Subject'] = report.get('email_subject', f"男足图文日报 {day} · 社媒竖版封面与双语图集") + (f'（{index}/{len(batches)}）' if len(batches) > 1 else '')
        if media_notice:
            msg.replace_header('Subject', str(msg['Subject']) + ' · 媒体待补')
        if report.get('delivery_phase') == 'supplement':
            msg.replace_header('Subject', '媒体补发 · ' + str(msg['Subject']))
        if report.get('partial_day'):
            msg.replace_header('Subject', str(msg['Subject']) + ' · 提前试跑')
        msg['From'], msg['To'] = sender, recipient
        msg['Date'], msg['Message-ID'] = formatdate(localtime=False), make_msgid()
        summary = '\n'.join(f"{m['league']}：{m['home']} {m['score']} {m['away']}" for m in report['matches'])
        text = f'本期图文已生成。附件包含可直接保存的1080×1312 竖版PNG，以及同批图片ZIP。\n\n{summary}\n\n'
        if report.get('standings_charts'):
            text += '积分榜图片也已附在邮件和 ZIP 中，按赛事列出积分、排名、场次和净胜球。\n'
        if media_notice:
            text += '\n媒体待补（所有比赛仍保留）：\n' + media_notice + '\n\n'
        text += '官方集锦链接（按比赛）：\n'
        for match in report['matches']:
            text += f"\n{match['home']} vs {match['away']}（附件 {match.get('poster', {}).get('filename', match['id'] + '.png')}）\n"
            clips = match.get('highlights', [])
            text += '\n'.join(f"{v['publisher']}：{v['url']}" for v in clips) if clips else '完整官方集锦暂缺'
            if match.get('gallery_url'):
                text += f"\n比赛图集（{len(match.get('gallery', []))}张）：{match['gallery_url']}"
            text += '\n'
        if report.get('partial_day'):
            text += f"提前试跑，实际截稿：{report['end']}，不是16:00完整版。\n"
        if len(batches) > 1:
            text += f'图片较多，已分成{len(batches)}封邮件，这是第{index}封。\n'
        if report['errors']:
            text += '\n本期资料缺项：\n' + '\n'.join(report['errors'])
        msg.set_content(text)
        cid = make_msgid(domain='football-daily.local')[1:-1]
        markup = '<html><body><h2>男足图文日报 ' + html.escape(day) + '</h2><p>1080×1312 竖版 PNG 和 ZIP 均在附件，可直接保存，无需打开网页。</p>'
        markup += '<p>' + html.escape(summary).replace('\n', '<br>') + '</p>'
        if report.get('standings_charts'):
            markup += '<p>另附积分榜 PNG：排名、积分、已赛场次与净胜球；浅绿标记本期参赛球队。积分为抓取时快照。</p>'
        if media_notice:
            markup += '<h3>媒体待补（所有比赛仍保留）</h3><p>' + html.escape(media_notice).replace('\n', '<br>') + '</p>'
        markup += '<h3>官方集锦 · 点击观看</h3><ul>'
        for match in report['matches']:
            markup += '<li><strong>' + html.escape(match['home'] + ' vs ' + match['away']) + '</strong><br>'
            clips = match.get('highlights', [])
            if clips:
                markup += '<br>'.join('<a href="' + html.escape(v['url'], quote=True) + '">官方集锦 · ' + html.escape(v['publisher']) + '</a>' for v in clips)
            else:
                markup += '完整官方集锦暂缺'
            if match.get('gallery_url'):
                markup += '<br><a href="' + html.escape(match['gallery_url'], quote=True) + '">比赛图集 · ' + str(len(match.get('gallery', []))) + '张照片</a>'
            markup += '<br><small>对应附件：' + html.escape(match.get('poster', {}).get('filename', match['id'] + '.png')) + '</small></li>'
        markup += '</ul>'
        if batch:
            markup += '<p>本批首张预览：</p><img style="width:100%;max-width:540px;height:auto" src="cid:' + cid + '">'
        if report.get('errors'):
            markup += '<h3>本期资料缺项</h3><p>' + html.escape('\n'.join(report['errors'])).replace('\n', '<br>') + '</p>'
        markup += '<p>图片含来源说明；部分配图为已标明的官方视频封面。完整文件请保存附件。</p></body></html>'
        msg.add_alternative(markup, subtype='html')
        if batch:
            with Image.open(batch[0]) as image:
                preview = image.convert('RGB')
                preview.thumbnail((540, 4000))
                data = io.BytesIO()
                preview.save(data, 'JPEG', quality=78)
            msg.get_payload()[-1].add_related(data.getvalue(), maintype='image', subtype='jpeg',
                                              cid='<' + cid + '>', disposition='inline', filename='preview.jpg')
            bundle = io.BytesIO()
            with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in batch:
                    archive.write(path, path.name)
            for path in batch:
                msg.add_attachment(path.read_bytes(), maintype='image', subtype='png', filename=path.name)
            suffix = f'-part{index}' if len(batches) > 1 else ''
            msg.add_attachment(bundle.getvalue(), maintype='application', subtype='zip',
                               filename=f'football-{day}-social{suffix}.zip')
        if len(msg.as_bytes()) > MAX_EMAIL_BYTES:
            raise ValueError('Encoded email exceeds safe Gmail limit; refusing partial delivery')
        messages.append(msg)
    return messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=os.environ.get('REPORT_DATE'))
    parser.add_argument('--out', default='docs')
    parser.add_argument('--correction', action='store_true', help='Explicit corrected edition of an already delivered report')
    parser.add_argument('--dry-run', help='Write EML files locally without logging in or sending')
    args = parser.parse_args()
    if not args.date:
        parser.error('Report date is required')
    folder = Path(args.out)
    report = json.loads((folder / 'reports' / f'{args.date}.json').read_text())
    from daily_delivery import load, save, phase, missing_media, waiting
    strict = os.environ.get('REQUIRE_COMPLETE_MEDIA') == 'true'
    if not args.dry_run:
        state = load()
        if args.correction:
            previous = state.get(report['day'], {})
            if previous.get('status') not in ('pending', 'complete') or not previous.get('accepted'):
                raise RuntimeError('Correction requires a previously accepted email, with no ambiguous SMTP reservation')
            selected = 'correction'
        else:
            selected = phase(report, state, strict)
        if not selected:
            if strict and missing_media(report) and not report.get('partial_day'):
                waiting(report['day'], strict=True)
            print('No new email delivery eligible')
            return
        report['delivery_phase'] = selected
        if selected == 'correction':
            report['email_subject'] = f"男足图文日报 {report['day']} · 球员中文名补正版"
        waiting(report['day'], strict=strict)
        state = load()
    sender = os.environ.get('SMTP_USERNAME', '')
    password = os.environ.get('SMTP_PASSWORD', '')
    recipient = os.environ.get('REPORT_EMAIL', sender)
    if args.dry_run:
        sender = sender or 'sender@example.invalid'
        recipient = recipient or 'recipient@example.invalid'
    elif not (sender and password and recipient):
        raise RuntimeError('Configure SMTP_USERNAME, SMTP_PASSWORD and REPORT_EMAIL in GitHub Secrets')
    messages = build_messages(report, folder, sender, recipient)
    if args.dry_run:
        target = Path(args.dry_run)
        target.mkdir(parents=True, exist_ok=True)
        for index, message in enumerate(messages, 1):
            (target / f'report-{index}.eml').write_bytes(message.as_bytes())
        print(f'Validated {len(messages)} email(s) with PNG/ZIP attachments; nothing sent')
        return
    # Fixed official endpoint, certificate validation mandatory. Never log credentials.
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=60) as smtp:
        smtp.login(sender, password.replace(' ', ''))
        entry = state[report['day']]
        # Reserve the entire immutable batch before any SMTP DATA. A crash or
        # ambiguous SMTP response must never cause an automatic duplicate.
        entry.update(status='reserved', phase=selected, total=len(messages), accepted=0)
        save(state)
        try:
            for message in messages:
                refused = smtp.send_message(message)
                if refused:
                    raise RuntimeError('SMTP refused recipient')
                entry['accepted'] += 1
                save(state)
        except Exception:
            entry['status'] = 'needs_review'
            save(state)
            raise
        entry['status'] = 'pending' if missing_media(report) else 'complete'
        save(state)
    print(f'Sent {len(messages)} attachment email(s)')


if __name__ == '__main__':
    main()
