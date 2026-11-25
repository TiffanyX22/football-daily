import json, re, sys
sys.path.insert(0, '.')
from agent import fetch, get_json, BASE
body = fetch('https://www.uefa.com/uefachampionsleague/match/2049625--real-madrid-vs-psv/')
for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', body, re.S):
    try: d = json.loads(raw)
    except ValueError: continue
    if d.get('@type') != 'LiveBlogPosting': continue
    ups = d.get('liveBlogUpdate', [])
    print('updates', len(ups), 'keys', sorted({k for u in ups for k in u}))
    for u in ups:
        img = u.get('image')
        if not img: continue
        name = (img if isinstance(img, str) else json.dumps(img))[-90:]
        text = ' | '.join(str(u.get(k, ''))[:160].replace('\n', ' ') for k in ('headline', 'articleBody', 'description', 'caption') if u.get(k))
        print(u.get('datePublished'), name, '::', text)
s = get_json(BASE + 'uefa.champions/summary?event=401915298')
for im in (s.get('article') or {}).get('images', []):
    print('ESPN', im.get('url'), im.get('width'), im.get('caption') or im.get('alt'), im.get('credit'))
print('ESPN keys', list(s.keys()))
for r in s.get('rosters', []):
    print('ROSTER', r.get('team', {}).get('displayName'), [p.get('athlete', {}).get('lastName') or p.get('athlete', {}).get('displayName') for p in r.get('roster', [])][:30])
