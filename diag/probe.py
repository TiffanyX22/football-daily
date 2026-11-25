import re, sys
sys.path.insert(0, '.')
from agent import fetch
body = fetch('https://www.uefa.com/uefachampionsleague/match/2049625--real-madrid-vs-psv/')
print('len', len(body))
for pat in [r'https://[a-z0-9.-]*uefa\.com/[^"\'\s<>]*(?:api|live|blog|feed|update|lineup|match)[^"\'\s<>]*', r'"[a-zA-Z]*(?:[Aa]pi|[Ee]ndpoint|[Bb]log|[Ll]ive)[a-zA-Z]*"\s*:\s*"[^"]{3,200}"',
            r'data-[a-z-]*(?:api|blog|live|feed|id)[a-z-]*="[^"]{1,200}"']:
    found = sorted(set(re.findall(pat, body)))
    print('##', pat[:40], len(found)); print('\n'.join('  ' + f[:220] for f in found[:60]))
imgs = sorted(set(re.findall(r'https://editorial\.uefa\.com/resources/[^"\s\']+?\.jpe?g', body)))
print('## editorial imgs in html', len(imgs)); print('\n'.join('  ' + i[-110:] for i in imgs[:80]))
for s in re.findall(r'<script[^>]+src="([^"]+)"', body)[:40]:
    print('script', s)
