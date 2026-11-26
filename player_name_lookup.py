"""Conservative public Wikidata lookup for previously unseen footballers."""
import functools
import json
from pathlib import Path
import threading
import unicodedata
import urllib.parse
import urllib.request

CACHE = Path(__file__).with_name('data') / 'player-name-cache.json'
_lock = threading.Lock()
_resolved = {}


def key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold() if c.isalpha())


def request(params):
    url = 'https://www.wikidata.org/w/api.php?' + urllib.parse.urlencode({'format': 'json', **params})
    req = urllib.request.Request(url, headers={'User-Agent': 'FootballDaily/1.0 (personal football digest; public names only)'})
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.load(response)


def pick(name, entities):
    matches = []
    for entity in entities.values():
        labels = entity.get('labels', {})
        english = labels.get('en', {}).get('value', '')
        aliases = [a['value'] for a in entity.get('aliases', {}).get('en', [])]
        description = entity.get('descriptions', {}).get('en', {}).get('value', '').casefold()
        if key(name) not in {key(english), *(key(a) for a in aliases)}:
            continue
        if not any(term in description for term in ('footballer', 'soccer player', 'football player')):
            continue
        chinese = next((labels.get(lang, {}).get('value') for lang in ('zh-hans', 'zh-cn', 'zh') if labels.get(lang, {}).get('value')), '')
        matches.append((chinese, entity['id']))
    return matches[0] if len(matches) == 1 and matches[0][0] and any('\u4e00' <= c <= '\u9fff' for c in matches[0][0]) else None


@functools.lru_cache(maxsize=1024)
def lookup(pid, name):
    if not pid or not name:
        return ''
    try:
        cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        old = cache.get(str(pid), {})
        if key(old.get('english', '')) == key(name):
            return old['chinese']
        search = request({'action': 'wbsearchentities', 'search': name, 'language': 'en', 'limit': 5})
        ids = [x['id'] for x in search.get('search', [])]
        if not ids:
            return ''
        entities = request({'action': 'wbgetentities', 'ids': '|'.join(ids), 'props': 'labels|aliases|descriptions', 'languages': 'en|zh-hans|zh-cn|zh'}).get('entities', {})
        selected = pick(name, entities)
        if selected:
            chinese, qid = selected
            with _lock:
                _resolved[str(pid)] = {'english': name, 'chinese': chinese, 'source': 'https://www.wikidata.org/wiki/' + qid}
            return chinese
    except Exception:
        pass
    return ''


def persist():
    if not _resolved:
        return
    with _lock:
        old = json.loads(CACHE.read_text()) if CACHE.exists() else {}
        old.update(_resolved)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(old, ensure_ascii=False, indent=2) + '\n')


def enrich_report(report):
    names = json.loads(Path(__file__).with_name('player-names.json').read_text())
    changed = set()
    for match in report['matches']:
        for event in match.get('timeline', []):
            for role in ('player', 'assist'):
                player = event.get(role)
                if not player:
                    continue
                chinese = names.get(str(player['id'])) or player.get('name_zh') or lookup(str(player['id']), player['name'])
                if chinese and chinese != player.get('name_zh'):
                    player['name_zh'] = chinese
                    changed.add(str(match['id']))
    persist()
    return changed
