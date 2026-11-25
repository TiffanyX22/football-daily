import re, sys
sys.path.insert(0, '.')
from agent import fetch
pat = r'(?:https://www\.(?:realmadrid|laliga)\.com)?/[A-Za-z0-9/_-]*(?:galeria|gallery|fotos|photos|fotogaleria|multimedia)[A-Za-z0-9/_?=.-]*'
for url in ['https://www.realmadrid.com/es-ES/noticias/futbol/primer-equipo',
            'https://www.realmadrid.com/en-US/news/football/first-team',
            'https://www.realmadrid.com/es-ES/galerias',
            'https://www.realmadrid.com/en-US/galleries',
            'https://www.realmadrid.com/sitemap.xml',
            'https://www.realmadrid.com/robots.txt',
            'https://www.laliga.com/multimedia',
            'https://www.laliga.com/robots.txt']:
    try:
        b = fetch(url)
        print('##', url, len(b))
        print('  links', sorted(set(re.findall(pat, b)))[:30])
        print('  imgs', len(set(re.findall(r'https://[^"\s\']+\.(?:jpe?g|webp|png)', b))), sorted(set(re.findall(r'https://[^"\s\']+\.(?:jpe?g|webp)', b)))[:5])
        if 'robots' in url or 'sitemap' in url:
            print(b[:1500])
        print('  next', '__NEXT_DATA__' in b, 'ld+json', b.count('ld+json'))
    except Exception as e:
        print('##', url, 'ERR', type(e).__name__, e)
