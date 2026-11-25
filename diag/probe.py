import re, sys
sys.path.insert(0, '.')
from agent import fetch
for sm in ['https://www.realmadrid.com/sitemap-es-ES.xml', 'https://www.realmadrid.com/sitemap-en-US.xml']:
    b = fetch(sm)
    locs = re.findall(r'<loc>([^<]+)</loc>', b)
    print('##', sm, len(locs))
    gal = [l for l in locs if re.search(r'galer|gallery|foto|photo', l, re.I)]
    print('  gallery-like', len(gal)); print('\n'.join('   ' + g for g in gal[-25:]))
    psv = [l for l in locs if 'psv' in l.lower()]
    print('  psv', '\n'.join('   ' + g for g in psv[-15:]))
    print('  sample', locs[-8:])
b = fetch('https://www.laliga.com/fotogalerias/home')
links = sorted(set(re.findall(r'/fotogalerias?/[A-Za-z0-9_-]+', b)))
print('## laliga fotogalerias', len(links)); print('\n'.join('   ' + l for l in links[:40]))
rm = [l for l in links if 'real-madrid' in l]
print('  rm', rm[:10])
if rm:
    page = fetch('https://www.laliga.com' + rm[0])
    imgs = sorted(set(re.findall(r'https://assets\.laliga\.com/assets/[^"\s\']+/large/[^"\s\']+\.jpe?g', page)))
    print('  ', rm[0], 'large imgs', len(imgs), imgs[:3])
    m = re.search(r'"(?:date|publishedAt|published_at|datePublished)"\s*:\s*"([^"]+)"', page); print('   date', m and m.group(1))
