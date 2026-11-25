"""Public official match photos and licensed broadcaster highlight discovery."""
import datetime as dt
import functools
import html
import json
import re
import unicodedata


def key(value):
    value = value.lower().replace('ø', 'o').replace('ł', 'l')
    value = ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))
    return re.sub('[^a-z0-9]', '', value)


ALIASES = {'Bodo/Glimt': 'Bodø/Glimt', 'LASK Linz': 'LASK', 'Feyenoord Rotterdam': 'Feyenoord',
           'FC Porto': 'Porto', 'PSV Eindhoven': 'PSV', 'Borussia Dortmund': 'B. Dortmund',
           'Slovan Bratislava': 'S. Bratislava', 'RB Leipzig': 'Leipzig'}


def json_script(body, variable):
    found = re.search(r'(?:var\s+)?' + variable + r'\s*=\s*({.*?});', body, re.S)
    return json.loads(found.group(1)) if found else {}


@functools.lru_cache(maxsize=2)
def cbs_catalog(fetch):
    body = fetch('https://www.youtube.com/@cbssportsgolazo/videos')
    data = json_script(body, 'ytInitialData')
    videos = []

    def walk(obj):
        if isinstance(obj, dict):
            if 'lockupViewModel' in obj:
                v = obj['lockupViewModel']
                title = v.get('metadata', {}).get('lockupMetadataViewModel', {}).get('title', {}).get('content', '')
                if 'Highlights' in title:
                    videos.append({'id': v.get('contentId'), 'title': title})
            if 'videoRenderer' in obj:
                v = obj['videoRenderer']
                title = ''.join(r.get('text', '') for r in v.get('title', {}).get('runs', []))
                if 'Highlights' in title:
                    videos.append({'id': v.get('videoId'), 'title': title})
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
    walk(data)
    return videos


def broadcast_highlights(home, away, kickoff, fetch):
    # These are licensed broadcaster highlights, not a UEFA-issued video.
    # Verify exact channel ID and publication date using the public watch page.
    aliases = dict(ALIASES, **{'Borussia Dortmund': 'Borussia Dortmund',
                             'Slovan Bratislava': 'Slovan Bratislava', 'RB Leipzig': 'RB Leipzig'})
    names = [key(aliases.get(n, n)) for n in (home, away)]
    try:
        candidates = cbs_catalog(fetch)
        for item in candidates:
            if not all(n in key(item['title']) for n in names):
                continue
            url = 'https://www.youtube.com/watch?v=' + item['id']
            player = json_script(fetch(url), 'ytInitialPlayerResponse')
            details = player.get('videoDetails', {})
            meta = player.get('microformat', {}).get('playerMicroformatRenderer', {})
            if details.get('channelId') != 'UCET00YnetHT7tOpu12v8jxg':
                continue
            published = dt.datetime.fromisoformat(meta.get('publishDate', '').replace('Z', '+00:00'))
            if not (kickoff <= published <= kickoff + dt.timedelta(days=2)):
                continue
            if player.get('playabilityStatus', {}).get('status') != 'OK':
                continue
            if not all(n in key(details.get('title', '')) for n in names):
                continue
            return [{'url': url, 'title': details['title'], 'publisher': 'CBS Sports Golazo（官方转播方，美国可看）',
                     'channel_id': details['channelId'], 'published': published.isoformat()}]
    except Exception:
        pass
    return []


@functools.lru_cache(maxsize=2)
def uefa_match_urls(fetch):
    body = fetch('https://www.uefa.com/uefachampionsleague/')
    return list(dict.fromkeys('https://www.uefa.com' + path for path in
                             re.findall(r'(/uefachampionsleague/match/\d+--[a-z0-9-]+/)', body)))


POST_MATCH = dt.timedelta(hours=3)


def shows_match(image, home, away):
    """Gallery mode: the match live blog also carries other fixtures, promos and
    player cutouts. Keep only files whose agency filename names both teams
    (e.g. real_madrid_c.f._v_psv_eindhoven..., fbl-eur-c1-real_madrid-psv...)."""
    name = key(image.rsplit('/', 1)[-1])
    return all(any(k and k in name for k in {key(team), key(ALIASES.get(team, team))}) for team in (home, away))


def image_urls(value):
    """liveBlogUpdate.image may be a URL, an ImageObject, or a list of either."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [u for u in (value.get('url') or value.get('contentUrl'),) if isinstance(u, str)]
    if isinstance(value, list):
        return [u for item in value for u in image_urls(item)]
    return []


def uefa_photos(home, away, kickoff, finished, fetch, reviewed_url=None, limit=2):
    try:
        names = [key(ALIASES.get(n, n)) for n in (home, away)]
        url = reviewed_url or next((u for u in uefa_match_urls(fetch) if all(n in key(u.split('--')[-1]) for n in names)), None)
        if not url:
            return []
        body = fetch(url)
        photos = []
        for raw in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', body, re.S):
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            if data.get('@type') != 'LiveBlogPosting':
                continue
            for post in data.get('liveBlogUpdate', []):
                for image in image_urls(post.get('image')):
                    if not image.startswith('https://editorial.uefa.com/resources/'):
                        continue
                    # Exclude player-card cutouts, training, and prior-match photos.
                    if not image.lower().endswith(('.jpg', '.jpeg')):
                        continue
                    published = dt.datetime.fromisoformat(post['datePublished'].replace('Z', '+00:00'))
                    # Gallery mode (limit > 2) also keeps full-time celebrations posted soon after the whistle.
                    if not kickoff <= published <= finished + (POST_MATCH if limit > 2 else dt.timedelta(0)):
                        continue
                    if limit > 2 and not shows_match(image, home, away):
                        continue
                    if image in {p['url'] for p in photos}:
                        continue
                    _, mime = fetch(image, binary=True)
                    if not mime.startswith('image/'):
                        continue
                    photos.append({'url': image, 'caption': f'{home} vs {away} · ' + ('本场赛中照片' if published <= finished else '终场后照片'),
                               'credit': 'UEFA 官方比赛中心 / 原摄影机构', 'source': post.get('url', url),
                                   'kind': 'match-photo', 'published': published.isoformat()})
                    if len(photos) >= limit:
                        return photos
        return photos
    except Exception:
        return []
