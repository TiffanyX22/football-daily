from pathlib import Path
import tempfile
import unittest
from PIL import Image
from poster import draw_poster, font, wrap, CONTENT


class PosterTests(unittest.TestCase):
    def test_multilingual_wrapping_fits_image_width(self):
        face = font(32)
        lines = wrap('很长的中文球队名称 / A very long international football team name ' * 4, face)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(face.getlength(line) <= CONTENT for line in lines))

    def test_missing_photo_still_exports_complete_png(self):
        match = {'id': 'demo', 'league': '英超', 'home': 'Brentford', 'away': 'Everton',
                 'score': '4–0', 'kickoff': '2026-11-23T12:00:00-08:00', 'photos': [],
                 'highlights': [], 'timeline': [], 'impact': '主队获得3分。', 'standings': []}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'poster.png'
            result = draw_poster(match, '2026-11-23', path, None, 'https://example.com')
            with Image.open(path) as image:
                self.assertEqual(image.format, 'PNG')
                self.assertEqual(image.width, 1080)
                self.assertEqual(image.height, result['height'])
                self.assertGreater(image.height, 1000)
            self.assertFalse(result['image_embedded'])

    def test_social_pages_preserve_complete_blocks_at_fixed_size(self):
        from poster import paginate
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.png'
            image = Image.new('RGB', (1080, 2000), '#123456')
            image.save(path)
            pages = paginate(path, [0, 800, 1500, 2000], 'Match')
            self.assertEqual(len(pages), 3)
            for page in pages:
                with Image.open(page) as result:
                    self.assertEqual(result.size, (1080, 1312))
                    self.assertEqual(result.getpixel((100, 70)), (18, 52, 86))
            self.assertFalse(path.exists())

    def test_compact_match_is_one_fixed_card(self):
        from social_match import draw_match
        match = {'home': 'Arsenal', 'away': 'Lens', 'league': '欧冠', 'score': '1–0',
                 'kickoff': '2026-11-24T12:00:00-08:00', 'id': 'demo', 'photos': [],
                 'timeline': [], 'standings': [], 'impact': '积分暂缺', 'highlights': []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'match.png'
            result = draw_match(match, '2026-11-24', path, None, 'https://example.com')
            with Image.open(path) as image:
                self.assertEqual(image.size, (1080, 1312))
            self.assertEqual(result['height'], 1312)
