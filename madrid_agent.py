"""Real Madrid men's full-time email agent; no paid services required."""
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import smtplib
import ssl
import subprocess

from agent import LA, UTC, LEAGUES, get_json, instant, make_match, fetch, render
from gallery import render_gallery
from madrid_gallery import enrich_gallery
from mail_report import build_messages
from social_match import draw_match

STATE = Path('data/madrid-delivery.json')
GALLERY_LIMIT = 30  # verified photos of this exact match on the 图集 page


def eligible(event, now, since, deliveries):
    competition = event.get('competitions', [{}])[0]
    return (str(event.get('id')) not in deliveries
            and any(str(c.get('team', {}).get('id')) == '86' for c in competition.get('competitors', []))
            and competition.get('status', {}).get('type', {}).get('completed', False)
            and since <= instant(event['date']) <= now
            and instant(event['date']) >= now - dt.timedelta(days=3))


def normalize(event):
    result = copy.deepcopy(event)
    for side in result['competitions'][0]['competitors']:
        if isinstance(side.get('score'), dict):
            side['score'] = side['score']['displayValue']
    return result


def checkpoint(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    # Serialize with the daily workflow. Persist the send reservation before SMTP:
    # an interrupted/ambiguous SMTP send is not automatically sent a second time.
    subprocess.run(['git', 'add', 'data/madrid-delivery.json', 'docs/real-madrid', 'docs/posters'], check=True)
    subprocess.run(['git', '-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                    'commit', '-m', 'Update Real Madrid match delivery'], check=True)
    subprocess.run(['git', 'push', 'origin', 'HEAD:main'], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--send', action='store_true')
    parser.add_argument('--out', default='docs')
    parser.add_argument('--event', help='Re-render one already-delivered match (card + gallery + pages)')
    parser.add_argument('--resend', action='store_true', help='With --event and --send: email the re-rendered match again on explicit request')
    args = parser.parse_args()
    now = dt.datetime.now(UTC)
    state = json.loads(STATE.read_text())
    since = instant(state['enabled_at'])
    events = get_json('https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/86/schedule')['events']
    if args.event:
        candidates = [e for e in events if str(e.get('id')) == args.event
                      and e['competitions'][0].get('status', {}).get('type', {}).get('completed')]
        if not candidates:
            raise SystemExit(f'Completed Real Madrid match {args.event} not found in schedule')
    else:
        candidates = sorted([e for e in events if eligible(e, now, since, state['deliveries'])], key=lambda e: e['date'])
    if not candidates:
        print('No new completed Real Madrid men matches; no email sent')
        return
    rules = json.loads(Path('publishers.json').read_text())
    out = Path(args.out)
    for event in candidates:
        slug = event['league']['slug']
        LEAGUES.setdefault(slug, {'esp.copa_del_rey': '西班牙国王杯', 'esp.super_cup': '西班牙超级杯',
                                 'fifa.club': '世俱杯', 'uefa.super_cup': '欧洲超级杯'}.get(slug, event['league']['name']))
        match = make_match(slug, normalize(event), since, now, rules, GALLERY_LIMIT, focus_team_id='86')
        if not match:
            continue
        enrich_gallery(match, GALLERY_LIMIT, fetch)
        day = instant(match['finished']).astimezone(LA).date().isoformat()
        root = out / 'posters' / day
        path = root / f"madrid-{match['id']}-zh-en.png"
        base = 'https://tiffanyx22.github.io/football-daily'
        if match.get('gallery'):
            match['gallery_url'] = f"{base}/real-madrid/{match['id']}-gallery.html"
        metadata = draw_match(match, day, path, fetch, base)
        if not metadata['image_embedded']:
            print('Waiting for a verified match photo:', match['id'])
            continue
        match['poster'] = {'filename': path.name, 'url': f'{base}/posters/{day}/{path.name}', **metadata}
        report = {'day': day, 'start': since.astimezone(LA).isoformat(), 'end': now.astimezone(LA).isoformat(),
                  'generated': now.astimezone(LA).isoformat(), 'matches': [match], 'errors': [], 'partial_day': False,
                  'coverage': '皇马男足赛后独立图文', 'email_subject': f"皇马赛后特辑 · {match['home']} {match['score']} {match['away']} · {day}"}
        dest = out / 'real-madrid'
        dest.mkdir(parents=True, exist_ok=True)
        for name in [match['id'], 'latest']:
            (dest / f'{name}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            (dest / f'{name}.html').write_text(render(report))
        if match.get('gallery_url'):
            for name in [match['id'], 'latest']:
                (dest / f'{name}-gallery.html').write_text(
                    render_gallery(match, day, f"{base}/real-madrid/{match['id']}.html#{match['id']}"))
        messages = build_messages(report, out, os.environ.get('SMTP_USERNAME', 'test@example.invalid'),
                                  os.environ.get('REPORT_EMAIL', 'test@example.invalid'))
        for msg in messages:
            msg.replace_header('Message-ID', f"<real-madrid-{match['id']}@football-daily.local>")
        if args.event:
            # Backfill: publish refreshed files; email only on explicit manual --resend.
            state['deliveries'].setdefault(match['id'], {})['rerendered_at'] = now.isoformat()
            checkpoint(state)
            if args.resend and args.send:
                sender, password, recipient = [os.environ.get(k) for k in ('SMTP_USERNAME', 'SMTP_PASSWORD', 'REPORT_EMAIL')]
                if not all((sender, password, recipient)):
                    raise RuntimeError('SMTP secrets required')
                for msg in messages:
                    msg.replace_header('Message-ID', f"<real-madrid-{match['id']}-resend-{int(now.timestamp())}@football-daily.local>")
                    msg.replace_header('Subject', '（补发·含图集）' + str(msg['Subject']))
                with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=60) as smtp:
                    smtp.login(sender, password.replace(' ', ''))
                    for msg in messages:
                        smtp.send_message(msg)
                state['deliveries'][match['id']]['resent_at'] = dt.datetime.now(UTC).isoformat()
                checkpoint(state)
                print('Resent Real Madrid graphic on manual request:', match['id'])
            if os.environ.get('GITHUB_OUTPUT'):
                with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                    output.write('publish=true\n')
            print(json.dumps({'event': match['id'], 'rerendered': True, 'gallery': len(match.get('gallery', [])),
                              'gallery_url': match.get('gallery_url'), 'image': str(path)}))
            continue
        if not args.send:
            print(json.dumps({'event': match['id'], 'photo': True, 'crests': metadata['team_crests_embedded'],
                              'highlights': len(match['highlights']),
                              'gallery': len(match.get('gallery', [])), 'image': str(path), 'dry_run': True}))
            continue
        sender, password, recipient = [os.environ.get(k) for k in ('SMTP_USERNAME', 'SMTP_PASSWORD', 'REPORT_EMAIL')]
        if not all((sender, password, recipient)):
            raise RuntimeError('SMTP secrets required')
        state['deliveries'][match['id']] = {'status': 'reserved', 'reserved_at': now.isoformat(),
                                            'note': 'Do not automatically resend reserved deliveries; inspect mailbox after an interrupted send.'}
        checkpoint(state)
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=60) as smtp:
                smtp.login(sender, password.replace(' ', ''))
                for msg in messages:
                    smtp.send_message(msg)
        except Exception:
            state['deliveries'][match['id']]['status'] = 'needs_review'
            checkpoint(state)
            raise
        state['deliveries'][match['id']] = {'status': 'sent', 'sent_at': dt.datetime.now(UTC).isoformat()}
        checkpoint(state)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write('publish=true\n')
        print('Sent Real Madrid full-time graphic:', match['id'])


if __name__ == '__main__':
    main()
