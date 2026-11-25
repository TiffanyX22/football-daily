import copy
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import agent
import daily_delivery as delivery
import mail_report


def fixture(missing=True):
    matches = []
    for i in range(9):
        absent = missing and i == 8
        matches.append(dict(id=str(i), home='RB Leipzig' if i == 8 else f'Home{i}',
                            away='Lens' if i == 8 else f'Away{i}', league='UCL',
                            slug='uefa.champions', score='1–0',
                            kickoff='2026-11-25T12:00:00-08:00',
                            finished='2026-11-25T14:00:00-08:00',
                            photos=[] if absent else [{'url': 'https://example.invalid/photo'}],
                            highlights=[] if absent else [{'url': 'https://example.invalid/video', 'publisher': 'example'}],
                            poster={'filename': f'{i}.png', 'image_embedded': not absent},
                            standings=['snapshot']))
    return dict(day='2026-11-25', matches=matches, errors=[], partial_day=False)


class DailyDeliveryTests(unittest.TestCase):
    def test_all_nine_retained_and_media_flagged(self):
        report = fixture()
        self.assertEqual(set(delivery.annotate(report)), {'8'})
        self.assertEqual(len(report['matches']), 9)
        self.assertEqual(report['media_status'], 'pending')
        self.assertEqual(len(report['matches'][8]['media_missing']), 3)
        self.assertEqual(delivery.phase(report, {}), 'initial')

    def test_empty_schedule_is_not_missing_media(self):
        report = fixture()
        report['matches'] = []
        self.assertEqual(delivery.annotate(report), {})
        self.assertEqual(delivery.phase(report, {}, True), 'initial')

    def test_strict_manual_wait_survives_retry(self):
        report = fixture()
        self.assertIsNone(delivery.phase(report, {}, True))
        state = {report['day']: {'status': 'waiting', 'strict': True}}
        self.assertIsNone(delivery.phase(report, state))
        self.assertEqual(delivery.phase(fixture(False), state), 'initial')

    def test_pending_then_single_supplement(self):
        report = fixture()
        state = {report['day']: {'status': 'pending'}}
        self.assertIsNone(delivery.phase(report, state))
        self.assertEqual(delivery.phase(fixture(False), state), 'supplement')
        for status in ('reserved', 'needs_review', 'complete'):
            state[report['day']]['status'] = status
            self.assertIsNone(delivery.phase(fixture(False), state))

    def test_historical_and_preview_never_email(self):
        report = fixture(False)
        report['day'] = '2026-11-24'
        self.assertIsNone(delivery.phase(report, {}))
        report['day'] = '2026-11-25'
        report['partial_day'] = True
        self.assertIsNone(delivery.phase(report, {}))

    def test_queue_excludes_delivered_and_exhausted(self):
        state = {'2026-11-24': {'status': 'pending'},
                 '2026-11-25': {'status': 'complete'},
                 '2026-11-26': {'status': 'pending', 'attempts': 8},
                 '2026-11-27': {'status': 'pending', 'last_attempt': '2026-11-28'},
                 '2026-11-28': {'status': 'waiting'}}
        self.assertEqual(delivery.next_pending(state), '2026-11-28')

    def test_refresh_preserves_match_set_scores_and_standings(self):
        report = fixture()
        before = copy.deepcopy(report)
        with patch('agent.get_json', return_value={}), patch('agent.discover_media',
              return_value=([{'url': 'https://example.invalid/new'}],
                            [{'url': 'https://example.invalid/clip'}])) as discover:
            agent.refresh_media(report, {})
        self.assertEqual(discover.call_count, 1)
        self.assertEqual(report['matches'][:8], before['matches'][:8])
        self.assertEqual(report['matches'][8]['score'], before['matches'][8]['score'])
        self.assertEqual(report['matches'][8]['standings'], before['matches'][8]['standings'])
        self.assertEqual(len(report['matches']), 9)

    def test_refresh_failure_preserves_snapshot(self):
        report = fixture()
        before = copy.deepcopy(report)
        with patch('agent.get_json', side_effect=TimeoutError):
            agent.refresh_media(report, {})
        self.assertEqual(report, before)

    def test_dst_fixed_local_window(self):
        for d, elapsed in [(dt.date(2027, 3, 14), 23), (dt.date(2027, 11, 7), 25)]:
            start, end = agent.window(d)
            self.assertEqual((start.hour, end.hour), (16, 16))
            self.assertEqual((end.astimezone(agent.UTC)-start.astimezone(agent.UTC)).total_seconds()/3600, elapsed)

    def test_initial_media_exception_does_not_drop_match(self):
        import sys
        from types import SimpleNamespace
        event = {'id': '8', 'name': 'Leipzig vs Lens',
                 'date': '2026-11-25T20:00:00Z',
                 'competitions': [{'status': {'type': {'completed': True}},
                    'competitors': [{'homeAway': 'home', 'score': '1', 'team': {'displayName': 'RB Leipzig'}},
                                    {'homeAway': 'away', 'score': '0', 'team': {'displayName': 'Lens'}}]}]}
        start, end = agent.window(dt.date(2026, 11, 25))
        with patch.dict(sys.modules, {'players': SimpleNamespace(timeline=lambda s: [])}), \
             patch('agent.get_json', return_value={}), \
             patch('agent.final_time', return_value=dt.datetime(2026,11,25,22,tzinfo=agent.UTC)), \
             patch('agent.standings', return_value=[]), \
             patch('agent.discover_media', side_effect=TimeoutError):
            result = agent.make_match('uefa.champions', event, start, end, {})
        self.assertEqual(result['id'], '8')
        self.assertEqual(result['score'], '1–0')
        self.assertEqual(result['photos'], [])
        self.assertEqual(result['highlights'], [])

    def test_mime_includes_every_match_and_missing_notice(self):
        from PIL import Image
        report = fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root/'posters'/report['day']
            folder.mkdir(parents=True)
            for match in report['matches']:
                Image.new('RGB', (10,10)).save(folder/match['poster']['filename'])
            messages = mail_report.build_messages(report, root, 'a@example.invalid', 'b@example.invalid')
            self.assertEqual(len(messages), 1)
            msg = messages[0]
            self.assertIn('媒体待补', str(msg['Subject']))
            body = msg.get_body(preferencelist=('plain',)).get_content()
            for match in report['matches']:
                self.assertIn(match['home'], body)
            self.assertIn('海报未嵌入图片', body)
            self.assertEqual(len(list(msg.iter_attachments())), 10)

    def test_smtp_reservation_and_ambiguous_failure(self):
        report = fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'reports').mkdir()
            (root/'reports'/f"{report['day']}.json").write_text(json.dumps(report))
            state = {report['day']: {'status': 'waiting'}}
            snapshots = []
            smtp = MagicMock()
            smtp.send_message.side_effect = TimeoutError
            def send(message):
                self.assertEqual(snapshots[-1][report['day']]['status'], 'reserved')
                raise TimeoutError
            smtp.send_message.side_effect = send
            with patch.dict(os.environ, {'SMTP_USERNAME':'sender@example.invalid',
                         'SMTP_PASSWORD':'fake','REPORT_EMAIL':'recipient@example.invalid',
                         'REQUIRE_COMPLETE_MEDIA':'false'}), patch('sys.argv',
                         ['mail_report.py','--date',report['day'],'--out',temp]), \
                 patch('daily_delivery.load', return_value=state), \
                 patch('daily_delivery.waiting'), \
                 patch('daily_delivery.save', side_effect=lambda s: snapshots.append(copy.deepcopy(s))), \
                 patch('mail_report.build_messages', return_value=[MagicMock()]), \
                 patch('mail_report.smtplib.SMTP_SSL') as transport:
                transport.return_value.__enter__.return_value = smtp
                with self.assertRaises(TimeoutError):
                    mail_report.main()
                self.assertEqual(state[report['day']]['status'], 'needs_review')
                mail_report.main()
                self.assertEqual(smtp.send_message.call_count, 1)


if __name__ == '__main__':
    unittest.main()
