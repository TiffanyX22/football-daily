import datetime as dt
import unittest
from delivery_watchdog import target, should_dispatch


class WatchdogTests(unittest.TestCase):
    def test_cutoff_dst_and_existing_reservations(self):
        now = dt.datetime(2026, 11, 26, 0, 5, tzinfo=dt.timezone.utc)
        self.assertEqual(target({}, now), '2026-11-25')
        self.assertEqual(target({'2026-11-25': {'status': 'reserved'}}, now), '')
        self.assertEqual(target({'2026-11-25': {'status': 'needs_review'}}, now), '')
        self.assertEqual(target({'2026-11-25': {'status': 'waiting'}}, now), '2026-11-25')
        before = dt.datetime(2026, 11, 26, 23, 59, tzinfo=dt.timezone.utc)
        self.assertEqual(target({'2026-11-25': {'status': 'complete'}}, before), '')
        after = dt.datetime(2026, 11, 27, 0, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(target({'2026-11-25': {'status': 'complete'}}, after), '2026-11-26')

    def test_inflight_and_backoff_and_pending_media(self):
        now = dt.datetime(2026, 11, 26, 1, tzinfo=dt.timezone.utc)
        self.assertFalse(should_dispatch('2026-11-25', [{'status': 'pending'}], now))
        recent = {'status': 'completed', 'created_at': '2026-11-26T00:55:00Z'}
        self.assertFalse(should_dispatch('2026-11-25', [recent], now))
        self.assertTrue(should_dispatch('2026-11-25', [], now))
        state = {'2026-11-25': {'status': 'pending', 'attempts': 1, 'last_attempt': '2026-11-26T00:50:00+00:00'}}
        self.assertEqual(target(state, now), '')
        state['2026-11-25']['last_attempt'] = '2026-11-25T23:00:00+00:00'
        self.assertEqual(target(state, now), '2026-11-25')
        state['2026-11-25']['attempts'] = 8
        self.assertEqual(target(state, now), '')
