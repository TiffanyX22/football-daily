import json
import unittest
from pathlib import Path

from gallery import render_gallery
from madrid_gallery import enrich_gallery


class MadridSelectionTests(unittest.TestCase):
    def test_psv_review_survives_rerender_and_preserves_cover(self):
        item = json.loads(Path('reviewed-media.json').read_text())['401915298']['madrid_gallery']
        cover = {'url': 'https://example.com/cover.jpg'}
        excluded = {'url': item['exclude'][0]}
        match = dict(id='401915298', photos=[cover, excluded], gallery=[cover, excluded])
        for _ in range(2):
            enrich_gallery(match, 30, self.fail)
        self.assertEqual(match['photos'][0], cover)
        self.assertNotIn(excluded, match['photos'] + match['gallery'])
        self.assertEqual(match['gallery'], item['photos'] + [cover])
        match.update(home='Real Madrid', away='PSV', score='5–1', league='欧冠', kickoff='2026-11-24')
        html = render_gallery(match, match['kickoff'], '/report')
        self.assertIn(item['instagram_post']['url'] + 'embed/', html)
        self.assertIn(item['club_report'], html)
