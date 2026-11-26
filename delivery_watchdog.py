"""Lightweight cloud recovery: inspect durable delivery state, then dispatch once."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
from zoneinfo import ZoneInfo

from daily_delivery import FIRST_DAY, MAX_RETRIES

LA = ZoneInfo('America/Los_Angeles')
ACTIVE = {'queued', 'in_progress', 'pending', 'waiting', 'requested'}


def target(state, now):
    local = now.astimezone(LA)
    due = local.date() - dt.timedelta(days=local.hour < 16)
    # Recover initial editions before spending time on optional media supplements.
    day = due
    while day >= dt.date.fromisoformat(FIRST_DAY):
        entry = state.get(str(day), {})
        if not entry or entry.get('status') == 'waiting':
            return str(day)
        day -= dt.timedelta(days=1)
    for day, entry in sorted(state.items()):
        if day > str(due) or entry.get('status') != 'pending' or entry.get('attempts', 0) >= MAX_RETRIES:
            continue
        last = entry.get('last_attempt')
        if not last or (now - dt.datetime.fromisoformat(last)).total_seconds() >= 3600:
            return day
    return ''


def should_dispatch(day, runs, now):
    if not day:
        return False
    if any(r.get('status') in ACTIVE for r in runs):
        return False
    # Failed runs back off to prevent immediate workflow_run loops.
    if runs:
        latest = max(runs, key=lambda r: r['created_at'])
        created = dt.datetime.fromisoformat(latest['created_at'].replace('Z', '+00:00'))
        if (now - created).total_seconds() < 600:
            return False
    return True


def api(path, payload=None):
    token = os.environ['GH_TOKEN']
    req = urllib.request.Request('https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + path,
          data=json.dumps(payload).encode() if payload is not None else None,
          headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                   'User-Agent': 'FootballDeliveryWatchdog', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read()
        return json.loads(data) if data else None


def main():
    now = dt.datetime.now(dt.timezone.utc)
    # Read state from the current default branch, never the stale triggering SHA.
    content = api('/contents/data/daily-delivery.json')
    import base64
    state = json.loads(base64.b64decode(content['content']))
    day = target(state, now)
    if not day:
        print('Delivery state healthy: no initial edition or media retry due')
        return
    runs = api('/actions/workflows/daily.yml/runs?per_page=15')['workflow_runs']
    if not should_dispatch(day, runs, now):
        print('Existing run active or within retry backoff; no duplicate dispatch')
        return
    api('/actions/workflows/daily.yml/dispatches', {'ref': 'main', 'inputs': {'report_date': day}})
    print('Dispatched recovery for', day)


if __name__ == '__main__':
    main()
