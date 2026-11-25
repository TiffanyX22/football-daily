import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from gallery import render_gallery
from media import uefa_photos


def jpeg():
    buffer = io.BytesIO()
    Image.new('RGB', (1280, 720), '#335544').save(buffer, 'JPEG')
    return buffer.getvalue()


MATCH = {'id': '42', 'league': '欧冠', 'home': 'Real Madrid', 'away': 'PSV <Eindhoven>', 'score': '5–1',
         'kickoff': '2026-11-24T12:00:00-08:00', 'highlights': [{'url': 'https://www.youtube.com/watch?v=x', 'publisher': 'CBS'}],
         'gallery': [{'url': f'https://img.example/{n}.jpg', 'caption': f'photo {n}', 'credit': 'EPA',
                      'source': 'https://www.espn.com/soccer/report/_/gameId/42'} for n in range(5)]}


class GalleryTests(unittest.TestCase):
    def test_gallery_lists_every_verified_photo_with_credit_and_escapes(self):
        page = render_gallery(MATCH, '2026-11-24', 'https://example.invalid/report.html')
        self.assertEqual(page.count('<figure>'), 5)
        self.assertIn('© EPA', page)
        self.assertIn('PSV &lt;Eindhoven&gt;', page)
        self.assertIn('官方视频集锦', page)

    def test_empty_gallery_says_missing_instead_of_substituting(self):
        page = render_gallery(dict(MATCH, gallery=[]), '2026-11-24', 'https://example.invalid/r.html')
        self.assertIn('暂未取得可核实的比赛照片', page)

    def test_uefa_photo_limit_is_configurable(self):
        posts = [{'image': f'https://editorial.uefa.com/resources/p{n}.jpeg', 'datePublished': '2026-11-24T20:30Z'} for n in range(8)]
        body = '<script type="application/ld+json">' + json.dumps({'@type': 'LiveBlogPosting', 'liveBlogUpdate': posts}) + '</script>'
        fetch = lambda url, binary=False: (b'x', 'image/jpeg') if binary else body
        args = ('A', 'B', dt.datetime(2026, 11, 24, 20, tzinfo=dt.timezone.utc),
                dt.datetime(2026, 11, 24, 22, tzinfo=dt.timezone.utc), fetch, 'https://www.uefa.com/m/')
        self.assertEqual(len(uefa_photos(*args)), 2)
        self.assertEqual(len(uefa_photos(*args, limit=6)), 6)

    def test_card_with_gallery_qr_keeps_fixed_size(self):
        from social_match import draw_match
        match = dict(MATCH, photos=MATCH['gallery'][:2], timeline=[], standings=[], impact='-',
                     team_logos={}, gallery_url='https://example.invalid/42-gallery.html')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'card.png'
            meta = draw_match(match, '2026-11-24', path, lambda url, binary=False: (jpeg(), 'image/jpeg'), 'https://example.invalid')
            self.assertEqual(Image.open(path).size, (1080, 1312))
            self.assertTrue(meta['image_embedded'])
