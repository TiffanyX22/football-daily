import unittest
from import_player_names import merge


class TransliterationsTests(unittest.TestCase):
    def test_only_requested_identity_and_chinese_name_accepted(self):
        requests = {'daily:2026-11-27': {'players': {'1': 'Sample Name'}}}
        cache = {}
        merge(requests, cache, [{'id': '1', 'english': 'Sample Name', 'chinese': '萨姆普尔'}])
        self.assertEqual(cache['1']['kind'], 'transliteration')
        for entry in [{'id':'2','english':'Sample Name','chinese':'姓名'},
                      {'id':'1','english':'Other Name','chinese':'姓名'},
                      {'id':'1','english':'Sample Name','chinese':'Sample Name'}]:
            with self.assertRaises(ValueError):
                merge(requests, cache, [entry])
