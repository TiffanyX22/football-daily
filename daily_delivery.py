"""Daily report media and durable delivery policy (independent of SMTP)."""
import datetime as dt
import json
from pathlib import Path
import subprocess

STATE = Path('data/daily-delivery.json')
FIRST_DAY = '2026-11-25'
MAX_RETRIES = 8


def missing_media(report):
    missing = {}
    for match in report['matches']:
        fields = []
        if not match.get('photos'):
            fields.append('缺已核实配图')
        if not match.get('highlights'):
            fields.append('缺官方集锦')
        if not match.get('poster', {}).get('image_embedded'):
            fields.append('海报未嵌入图片')
        if fields:
            missing[str(match['id'])] = fields
    return missing


def annotate(report):
    missing = missing_media(report)
    for match in report['matches']:
        match['media_missing'] = missing.get(str(match['id']), [])
    report['media_status'] = 'pending' if missing else 'complete'
    return missing


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    # The shared workflow concurrency group serializes writers. Persist before SMTP.
    subprocess.run(['git', 'add', str(STATE)], check=True)
    subprocess.run(['git', 'commit', '-m', 'Record daily email delivery state'], check=True)
    subprocess.run(['git', 'push'], check=True)


def phase(report, state, strict=False):
    day = report['day']
    if day < FIRST_DAY or report.get('partial_day'):
        return None
    entry = state.get(day, {})
    if entry.get('status') in ('reserved', 'needs_review', 'complete'):
        return None
    missing = missing_media(report)
    if entry.get('status') == 'pending':
        return 'supplement' if not missing else None
    if (strict or entry.get('strict')) and missing:
        return None
    return 'initial'


def next_pending(state):
    candidates = [(entry.get('last_attempt', ''), day) for day, entry in state.items()
                  if day >= FIRST_DAY and entry.get('status') in ('pending', 'waiting')
                  and entry.get('attempts', 0) < MAX_RETRIES]
    return min(candidates)[1] if candidates else ''


def next_scheduled_report(state, latest_due, reports=Path('docs/reports')):
    """Pick one missing edition before using a backup slot for media retries."""
    day = latest_due
    first = dt.date.fromisoformat(FIRST_DAY)
    while day >= first:
        key = day.isoformat()
        if key not in state and not (reports / f'{key}.json').is_file():
            return key, False
        day -= dt.timedelta(days=1)
    pending = next_pending(state)
    return pending, bool(pending)


def retry_attempt(day):
    state = load()
    entry = state[day]
    entry['attempts'] = entry.get('attempts', 0) + 1
    entry['last_attempt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save(state)


def waiting(day, strict=False):
    state = load()
    if day < FIRST_DAY:
        return
    if day not in state:
        state[day] = {'status': 'waiting', 'attempts': 0, 'strict': strict}
        save(state)
    elif strict and state[day].get('status') == 'waiting' and not state[day].get('strict'):
        state[day]['strict'] = True
        save(state)


if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'next':
        print(next_pending(load()))
    elif sys.argv[1] == 'attempt':
        retry_attempt(sys.argv[2])
