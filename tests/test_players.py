import unittest
from players import timeline, label


class PlayerEventsTests(unittest.TestCase):
    def test_explicit_assist_uses_match_number_and_scorer_is_separate(self):
        a = {'id': '319368', 'displayName': 'Antonio Nusa'}
        b = {'id': '222176', 'displayName': 'Christopher Nkunku'}
        event = {'scoringPlay': True, 'participants': [{'athlete': a}, {'athlete': b}],
                 'text': 'Goal! Assisted by Christopher Nkunku following a fast break.'}
        summary = {'rosters': [{'roster': [{'athlete': a, 'jersey': '7'}, {'athlete': b, 'jersey': '28'}]}], 'keyEvents': [event]}
        result = timeline(summary)[0]
        self.assertEqual(result['player']['id'], '319368')
        self.assertEqual(result['assist']['number'], '28')
        self.assertIn('安东尼奥·努萨（Antonio Nusa）', label(result['player']))
        event['text'] = 'Goal!'
        self.assertIsNone(timeline(summary)[0]['assist'])
        summary['rosters'] = []
        self.assertIn('号码未核实', label(timeline(summary)[0]['player']))
