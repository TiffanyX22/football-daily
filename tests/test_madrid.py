import copy
import datetime as dt
import unittest
from madrid_agent import eligible, normalize


class MadridTests(unittest.TestCase):
    def test_only_new_completed_mens_team_id_is_eligible(self):
        now = dt.datetime(2026, 11, 24, 23, tzinfo=dt.timezone.utc)
        event = {'id': '42', 'date': '2026-11-24T20:00Z', 'competitions': [{'status': {'type': {'completed': True}}, 'competitors': [{'team': {'id': '86'}, 'score': {'displayValue': '5'}}]}]}
        since = now - dt.timedelta(days=1)
        self.assertTrue(eligible(event, now, since, {}))
        self.assertFalse(eligible(event, now, since, {'42': {'status': 'sent'}}))
        self.assertFalse(eligible(event, now, since, {'42': {'status': 'reserved'}}))
        self.assertFalse(eligible(event, now, now, {}))
        other = copy.deepcopy(event)
        other['competitions'][0]['competitors'][0]['team']['id'] = '999'
        self.assertFalse(eligible(other, now, since, {}))
        other = copy.deepcopy(event)
        other['competitions'][0]['status']['type']['completed'] = False
        self.assertFalse(eligible(other, now, since, {}))
        self.assertEqual(normalize(event)['competitions'][0]['competitors'][0]['score'], '5')
        self.assertIsInstance(event['competitions'][0]['competitors'][0]['score'], dict)
