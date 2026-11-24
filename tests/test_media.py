import datetime as dt
import json
import unittest
from media import key, uefa_photos


class OfficialMediaTests(unittest.TestCase):
    def test_norwegian_and_short_team_names_normalize(self):
        self.assertEqual(key('Bodø/Glimt'), key('Bodo Glimt'))

    def test_only_in_match_editorial_photos_are_selected(self):
        posts = [
            {'image': 'https://img.uefa.com/imgml/TP/players/head.jpg', 'datePublished': '2026-11-24T20:30Z'},
            {'image': 'https://editorial.uefa.com/resources/prior-match.jpeg', 'datePublished': '2026-11-24T18:00Z'},
            {'image': 'https://editorial.uefa.com/resources/current-match.jpeg', 'datePublished': '2026-11-24T20:30Z'}]
        body = '<script type="application/ld+json">' + json.dumps({'@type': 'LiveBlogPosting', 'liveBlogUpdate': posts}) + '</script>'
        def fetch(url, binary=False):
            return (b'photo', 'image/jpeg') if binary else body
        result = uefa_photos('A', 'B', dt.datetime(2026,11,24,20,tzinfo=dt.timezone.utc),
                             dt.datetime(2026,11,24,22,tzinfo=dt.timezone.utc), fetch,
                             'https://www.uefa.com/uefachampionsleague/match/real-match/')
        self.assertEqual(len(result), 1)
        self.assertIn('current-match', result[0]['url'])
