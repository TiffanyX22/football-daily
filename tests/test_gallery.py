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
        posts = [{'image': f'https://editorial.uefa.com/resources/a_v_b_{n}.jpeg', 'datePublished': '2026-11-24T20:30Z'} for n in range(8)]
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


class GalleryWindowTests(unittest.TestCase):
    def test_gallery_mode_keeps_post_match_and_image_objects_but_daily_does_not(self):
        posts = [{'image': 'https://editorial.uefa.com/resources/live/real_madrid_c.f._v_psv_eindhoven_md5.jpeg', 'datePublished': '2026-11-24T20:30Z'},
                 {'image': {'@type': 'ImageObject', 'url': 'https://editorial.uefa.com/resources/obj/fbl-eur-c1-real_madrid-psv.jpeg'}, 'datePublished': '2026-11-24T21:00Z'},
                 {'image': 'https://editorial.uefa.com/resources/after/topshot-fbl-eur-c1-real_madrid-psv.jpeg', 'datePublished': '2026-11-24T23:30Z'},
                 {'image': 'https://editorial.uefa.com/resources/other/fbl-fc_porto-eur-c1-feyenoord-porto.jpeg', 'datePublished': '2026-11-24T21:10Z'},
                 {'image': 'https://editorial.uefa.com/resources/promo/ucl_24x27_-_goal_of_the_day_x4.jpeg', 'datePublished': '2026-11-24T22:30Z'},
                 {'image': 'https://editorial.uefa.com/resources/getty/gettyimages-2306715922.jpeg', 'datePublished': '2026-11-24T21:20Z'},
                 {'image': 'https://editorial.uefa.com/resources/nextday.jpeg', 'datePublished': '2026-11-25T09:00Z'}]
        body = '<script type="application/ld+json">' + json.dumps({'@type': 'LiveBlogPosting', 'liveBlogUpdate': posts}) + '</script>'
        fetch = lambda url, binary=False: (b'x', 'image/jpeg') if binary else body
        args = ('A', 'B', dt.datetime(2026, 11, 24, 20, tzinfo=dt.timezone.utc),
                dt.datetime(2026, 11, 24, 22, tzinfo=dt.timezone.utc), fetch, 'https://www.uefa.com/m/')
        self.assertEqual(len(uefa_photos(*args)), 2)
        gallery = uefa_photos('Real Madrid', 'PSV Eindhoven', *args[2:], limit=30)
        self.assertEqual([p['url'].split('/')[4] for p in gallery], ['live', 'obj', 'after'])
        self.assertIn('终场后', gallery[2]['caption'])


class MadridOnlyTests(unittest.TestCase):
    def test_focus_keeps_only_posts_about_real_madrid(self):
        from media import focus_terms
        focus = (focus_terms(['Real Madrid', 'Madrid', 'Los Blancos', 'Courtois', 'Mbappé', 'Bernardo Silva', 'Silva']),
                 focus_terms(['PSV Eindhoven', 'PSV', 'Dest', 'Perisic', 'Perišić']))
        base = 'https://editorial.uefa.com/resources/{}/{}'
        posts = [
            ('a', 'real_madrid_c.f._v_psv_eindhoven_md5.jpeg', "UEFA Champions League: Real Madrid-PSV 84'", 'Mbappé scores for Real Madrid!'),
            ('b', 'fbl-eur-c1-real_madrid-psv.jpeg', "UEFA Champions League: Real Madrid-PSV 32'", 'Perišić scores for PSV!'),
            ('c', 'real_madrid_c.f._v_psv_eindhoven_md5.jpeg', 'Peter Bosz, PSV coach: &quot;You could see it&quot;', ''),
            ('d', 'gettyimages-2306715922.jpeg', 'More from Madrid&#39;s Bernardo Silva, speaking to UEFA', ''),
            ('e', 'real_madrid_c.f._v_psv_eindhoven_md5.jpeg', 'Stay with us for reaction from both sides.', ''),
            ('f', 'gettyimages-1.jpeg', 'More from Sergiño Dest: &quot;Madrid changed some players&quot;', ''),
            ('g', 'ucl_24x27_-_goal_of_the_day.jpeg', 'Jude Bellingham, Luis Milla? Vote for your Goal of the Day', '')]
        updates = [{'image': base.format(i, f), 'headline': h, 'articleBody': b, 'datePublished': '2026-11-24T21:30Z'} for i, f, h, b in posts]
        body = '<script type="application/ld+json">' + json.dumps({'@type': 'LiveBlogPosting', 'liveBlogUpdate': updates}) + '</script>'
        fetch = lambda url, binary=False: (b'x', 'image/jpeg') if binary else body
        kept = uefa_photos('Real Madrid', 'PSV Eindhoven', dt.datetime(2026, 11, 24, 20, tzinfo=dt.timezone.utc),
                           dt.datetime(2026, 11, 24, 22, tzinfo=dt.timezone.utc), fetch, 'https://www.uefa.com/m/', 30, focus)
        self.assertEqual([p['url'].split('/')[4] for p in kept], ['a', 'd'])
