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
    day = report['day']
    paths = [folder / 'posters' / day / (m['id'] + '.png') for m in report['matches']]
    batches = groups(paths) or [[]]
    messages = []
    for index, batch in enumerate(batches, 1):
        msg = EmailMessage()
        msg['Subject'] = f"男足图文日报 {day}" + (f'（{index}/{len(batches)}）' if len(batches) > 1 else '')
        if report.get('partial_day'):
            msg.replace_header('Subject', str(msg['Subject']) + ' · 提前试跑')
        msg['From'], msg['To'] = sender, recipient
        msg['Date'], msg['Message-ID'] = formatdate(localtime=False), make_msgid()
        summary = '\n'.join(f"{m['league']}：{m['home']} {m['score']} {m['away']}" for m in report['matches'])
        text = f'本期图文已生成。附件包含可直接保存的原尺寸PNG，以及同批图片ZIP。\n\n{summary}\n\n'
        if report.get('partial_day'):
            text += f"提前试跑，实际截稿：{report['end']}，不是16:00完整版。\n"
        if len(batches) > 1:
            text += f'图片较多，已分成{len(batches)}封邮件，这是第{index}封。\n'
        if report['errors']:
            text += '\n本期资料缺项：\n' + '\n'.join(report['errors'])
        msg.set_content(text)
        cid = make_msgid(domain='football-daily.local')[1:-1]
        markup = '<html><body><h2>男足图文日报 ' + html.escape(day) + '</h2><p>原尺寸 PNG 和 ZIP 均在附件，可直接保存，无需打开网页。</p>'
        markup += '<p>' + html.escape(summary).replace('\n', '<br>') + '</p>'
        if batch:
            markup += '<p>本批首张预览：</p><img style="width:100%;max-width:540px;height:auto" src="cid:' + cid + '">'
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
                               filename=f'football-{day}{suffix}.zip')
        if len(msg.as_bytes()) > MAX_EMAIL_BYTES:
            raise ValueError('Encoded email exceeds safe Gmail limit; refusing partial delivery')
        messages.append(msg)
    return messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=os.environ.get('REPORT_DATE'))
    parser.add_argument('--out', default='docs')
    parser.add_argument('--dry-run', help='Write EML files locally without logging in or sending')
    args = parser.parse_args()
    if not args.date:
        parser.error('Report date is required')
    folder = Path(args.out)
    report = json.loads((folder / 'reports' / f'{args.date}.json').read_text())
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
        for message in messages:
            smtp.send_message(message)
    print(f'Sent {len(messages)} attachment email(s)')


if __name__ == '__main__':
    main()
