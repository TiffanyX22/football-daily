import datetime as dt
import unittest
from unittest.mock import patch
import agent


class AgentTests(unittest.TestCase):
    def test_dst_windows_follow_calendar_not_24_hours(self):
        start, end = agent.window(dt.date(2026, 11, 1))
        self.assertEqual((end.astimezone(agent.UTC) - start.astimezone(agent.UTC)).total_seconds(), 25 * 3600)
        start, end = agent.window(dt.date(2026, 3, 8))
        self.assertEqual((end.astimezone(agent.UTC) - start.astimezone(agent.UTC)).total_seconds(), 23 * 3600)
        self.assertEqual((start.hour, end.hour), (16, 16))

    def test_ignores_unrelated_news_photos(self):
        summary = {'article': {'gameId': 'other', 'type': 'Recap', 'images': [{'url': 'https://x/photo/test.jpg'}]}}
        with patch.object(agent, 'valid_photo') as check:
            self.assertEqual(agent.photos(summary, 'our-match'), [])
            check.assert_not_called()

    def test_latest_terminal_event_wins(self):
        summary = {'keyEvents': [
            {'type': {'type': 'end-regular-time'}, 'wallclock': '2026-11-23T22:00Z'},
            {'type': {'type': 'end-extra-time'}, 'wallclock': '2026-11-23T22:40Z'}]}
        self.assertEqual(agent.final_time(summary).hour, 22)
        self.assertEqual(agent.final_time(summary).minute, 40)

    def test_no_terminal_time_is_not_guessed(self):
        self.assertIsNone(agent.final_time({'keyEvents': []}))

    def test_html_is_escaped(self):
        self.assertEqual(agent.esc('<script>'), '&lt;script&gt;')

    def test_independent_source_flags_missing_match(self):
        fixture = '''<tr><th><h2>Premier League</h2></th></tr>
        <tr><td class="finished"></td><td class="team homeTeam">Brentford</td>
        <td class="score"><em>4</em>-<em>0</em></td><td class="team awayTeam">Everton</td></tr>'''
        with patch.object(agent, 'fetch', return_value=fixture):
            audit = agent.reconcile(dt.date(2026, 11, 23), [], ['eng.1'])
        self.assertEqual(audit['expected'], 1)
        self.assertEqual(len(audit['findings']), 1)

    def test_score_conflict_is_not_silent(self):
        fixture = '''<tr><th><h2>Premier League</h2></th></tr>
        <tr><td class="finished"></td><td class="team homeTeam">Brentford</td>
        <td class="score"><em>4</em>-<em>0</em></td><td class="team awayTeam">Everton</td></tr>'''
        with patch.object(agent, 'fetch', return_value=fixture):
            audit = agent.reconcile(dt.date(2026, 11, 23), [{'slug': 'eng.1', 'home': 'Brentford', 'away': 'Everton', 'score': '3–0'}], ['eng.1'])
        self.assertIn('比分冲突', audit['findings'][0])


if __name__ == '__main__':
    unittest.main()
