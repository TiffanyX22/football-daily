from email import policy
from email.parser import BytesParser
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from PIL import Image
from mail_report import build_messages


class MailReportTests(unittest.TestCase):
    def test_email_contains_actual_png_zip_and_inline_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            root = folder / 'posters' / '2026-11-23'
            root.mkdir(parents=True)
            Image.new('RGB', (1080, 1800), '#123456').save(root / 'test.png')
            Image.new('RGB', (1080, 2600), '#234567').save(root / 'standings-demo.png')
            report = {'standings_charts': [{'filename': 'standings-demo.png'}], 'day': '2026-11-23', 'matches': [{'id': 'test', 'league': '英超',
                      'home': 'A', 'away': 'B', 'score': '2–0',
                      'highlights': [{'publisher': 'Official broadcaster', 'url': 'https://example.com/highlights?match=1&date=2'}]}], 'errors': []}
            mail = build_messages(report, folder, 'a@example.invalid', 'b@example.invalid')[0]
            parsed = BytesParser(policy=policy.default).parsebytes(mail.as_bytes())
            attachments = {p.get_filename(): p for p in parsed.iter_attachments()}
            self.assertEqual(set(attachments), {'test.png', 'standings-demo.png', 'football-2026-11-23-zh-en.zip'})
            self.assertEqual(attachments['test.png'].get_payload(decode=True), (root / 'test.png').read_bytes())
            with zipfile.ZipFile(io.BytesIO(attachments['football-2026-11-23-zh-en.zip'].get_payload(decode=True))) as archive:
                self.assertIn('standings-demo.png', archive.namelist())
                self.assertEqual(archive.read('test.png'), (root / 'test.png').read_bytes())
            self.assertIn('cid:', parsed.get_body(('html',)).get_content())
            self.assertIn('href="https://example.com/highlights?match=1&amp;date=2"', parsed.get_body(('html',)).get_content())
            self.assertIn('https://example.com/highlights?match=1&date=2', parsed.get_body(('plain',)).get_content())
            self.assertTrue(any(p.get_content_type() == 'image/jpeg' and p['Content-ID'] for p in parsed.walk()))
