"""Accept translated proper names only for identities requested by the agent."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess


def merge(requests, cache, entries):
    allowed = {str(pid): name for request in requests.values() for pid, name in request['players'].items()}
    if not isinstance(entries, list) or len(entries) > 100:
        raise ValueError('Expected at most 100 requested player names')
    updated = 0
    for entry in entries:
        pid = str(entry['id'])
        chinese = entry.get('chinese', '').strip()
        if allowed.get(pid) != entry.get('english'):
            raise ValueError('Player identity is not in the current request queue')
        if not chinese or len(chinese) > 100 or not any('\u4e00' <= c <= '\u9fff' for c in chinese) or any(c in chinese for c in '<>\r\n'):
            raise ValueError('Invalid Chinese transliteration')
        cache[pid] = {'english': entry['english'], 'chinese': chinese, 'kind': 'transliteration',
                      'source': 'Google Apps Script LanguageApp', 'updated_at': dt.datetime.now(dt.timezone.utc).isoformat()}
        updated += 1
    return updated


def main():
    requests = json.loads(Path('data/player-name-requests.json').read_text())
    cache_path = Path('data/player-name-cache.json')
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    entries = json.loads(os.environ['TRANSLATED_NAMES'])
    # A delayed duplicate is harmless after the first import cleared its queue.
    if not requests:
        print('No player name requests pending')
        return
    merge(requests, cache, entries)
    complete = [r for r in requests.values() if all(cache.get(str(pid), {}).get('english') == name for pid, name in r['players'].items())]
    requests = {k: r for k, r in requests.items() if r not in complete}
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + '\n')
    Path('data/player-name-requests.json').write_text(json.dumps(requests, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(['git', 'add', 'data/player-name-cache.json', 'data/player-name-requests.json'], check=True)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode != 0
    if changed:
        subprocess.run(['git', '-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                        'commit', '-m', 'Cache automatically transliterated football player names'], check=True)
        subprocess.run(['git', 'push'], check=True)
    for request in complete:
        args = ['gh', 'workflow', 'run', 'daily.yml', '-f', 'report_date=' + request['day']] if request['kind'] == 'daily' else ['gh', 'workflow', 'run', 'real-madrid.yml']
        subprocess.run(args, check=True)


if __name__ == '__main__':
    main()
