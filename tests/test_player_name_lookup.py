import copy
import unittest
from unittest.mock import patch
from player_name_lookup import pick, enrich_report


class NameLookupTests(unittest.TestCase):
    def test_only_unique_exact_footballer_with_chinese_is_accepted(self):
        person = {'id': 'Q1', 'labels': {'en': {'value': 'Anthony Gordon'}, 'zh-hans': {'value': '安东尼·戈登'}},
                  'descriptions': {'en': {'value': 'English footballer'}}}
        self.assertEqual(pick('Anthony Gordon', {'Q1': person}), ('安东尼·戈登', 'Q1'))
        self.assertIsNone(pick('A different player', {'Q1': person}))
        other = copy.deepcopy(person)
        other['id'] = 'Q2'
        self.assertIsNone(pick('Anthony Gordon', {'Q1': person, 'Q2': other}))
        person['descriptions']['en']['value'] = 'British actor'
        self.assertIsNone(pick('Anthony Gordon', {'Q1': person}))

    def test_backfill_preserves_scores_numbers_and_english(self):
        report = {'matches': [{'id': '1', 'score': '2–0', 'timeline': [{'player': {
                    'id': '268782', 'name': 'Anthony Gordon', 'number': '10', 'name_zh': ''}}]}]}
        with patch('player_name_lookup.persist'):
            self.assertEqual(enrich_report(report), {'1'})
        player = report['matches'][0]['timeline'][0]['player']
        self.assertEqual(player['name_zh'], '安东尼·戈登')
        self.assertEqual((player['name'], player['number']), ('Anthony Gordon', '10'))
        self.assertEqual(report['matches'][0]['score'], '2–0')
