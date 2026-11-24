"""Event player labels: match-roster shirt numbers and explicit assist attribution."""
import json
from pathlib import Path


def timeline(summary):
    names = json.loads(Path(__file__).with_name('player-names.json').read_text())
    roster = {}
    for team in summary.get('rosters', []):
        for entry in team.get('roster', []):
            athlete = entry.get('athlete', {})
            roster[str(athlete.get('id'))] = {**athlete, 'jersey': entry.get('jersey')}

    def player(athlete):
        pid = str(athlete.get('id', ''))
        return {'id': pid, 'name': athlete.get('displayName', ''),
                'name_zh': names.get(pid, ''), 'number': roster.get(pid, {}).get('jersey')}

    result = []
    for event in summary.get('keyEvents', []):
        if not (event.get('scoringPlay') or event.get('type', {}).get('type') in ('red-card', 'yellow-red-card')):
            continue
        participants = [p['athlete'] for p in event.get('participants', []) if p.get('athlete')]
        # The provider lists the scorer first. Additional participants are not
        # assumed to be assistants: require the explicit Assisted by statement.
        assist = None
        clause = event.get('text', '').partition('Assisted by ')[2]
        if clause:
            candidates = list(roster.values()) + participants
            for athlete in sorted(candidates, key=lambda a: len(a.get('displayName', '')), reverse=True):
                name = athlete.get('displayName', '')
                if name and clause.startswith(name) and (len(clause) == len(name) or clause[len(name)] in ' .,;'):
                    assist = player(athlete)
                    break
        scorer = player(participants[0]) if participants else None
        result.append({'minute': event.get('clock', {}).get('displayValue', ''),
                       'type': event.get('type', {}).get('text', ''),
                       'players': participants[0].get('displayName', '') if participants else '',
                       'player': scorer, 'assist': assist,
                       'scoring': bool(event.get('scoringPlay')),
                       'text': event.get('text', '')})
    return result


def label(player):
    if not player:
        return '球员资料暂缺'
    number = '#' + str(player['number']) if player.get('number') else '号码未核实'
    return f"{number} {player.get('name_zh') or '中文名待核实'}（{player['name']}）"
