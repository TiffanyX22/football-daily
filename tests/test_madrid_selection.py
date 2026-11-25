import unittest

from madrid_gallery import CLUB_SITE, REPORT_PATH, enrich_gallery


class MadridSelectionTests(unittest.TestCase):
    def test_unconfigured_match_adds_album_in_order_only_once(self):
        match = dict(id='new', kickoff='2026-11-24T12:00:00-08:00', home='Real Madrid',
                     away='PSV Eindhoven', gallery=[], photos=[])
        path = REPORT_PATH + 'cronica-24-11-2026'
        teams = ''.join(f'<p class="rm-game__team rm-game__team--{side}">{match[side]}</p>'
                        for side in ['home', 'away'])
        images = ''.join(f'<img class="rm-gallery__img" src="https://assets.realmadrid.com/is/image/realmadrid/{i}?wid=148">'
                         for i in range(12))
        pages = {CLUB_SITE + '/en-US/football/first-team/home': f'<a href="{path}">Match</a>',
                 CLUB_SITE + path: teams + images}
        for _ in range(2):
            enrich_gallery(match, 30, pages.__getitem__)
        self.assertEqual(len(match['gallery']), 8)
        self.assertTrue(match['gallery'][0]['url'].endswith('/0?wid=1200'))
        self.assertEqual(match['club_album'], CLUB_SITE + path)
        other = dict(match, away='Barcelona', gallery=[], photos=[])
        enrich_gallery(other, 30, pages.__getitem__)
        self.assertEqual(other['gallery'], [])
