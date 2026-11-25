"""Add the club's matchday photo selection to the Madrid gallery."""
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from agent import normalized

CLUB_SITE = 'https://www.realmadrid.com'
REPORT_PATH = '/en-US/news/football/first-team/reports/'
CLUB_PHOTO_LIMIT = 8


class AlbumPhotos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag != 'img':
            return
        attrs = dict(attrs)
        if 'rm-gallery__img' not in attrs.get('class', '').split():
            return
        src = urlsplit(attrs.get('src', ''))
        if (src.scheme, src.netloc) != ('https', 'assets.realmadrid.com'):
            return
        if src.path.startswith('/is/image/realmadrid/'):
            url = src._replace(query='wid=1200', fragment='').geturl()
            if url not in self.urls:
                self.urls.append(url)


def club_photos(match, fetch, known_report=None):
    day = dt.datetime.fromisoformat(match['kickoff']).astimezone(ZoneInfo('Europe/Madrid'))
    if known_report:
        candidates = [known_report]
    else:
        index = fetch(CLUB_SITE + '/en-US/football/first-team/home')
        paths = re.findall(r'href="(' + REPORT_PATH + r'[a-zA-Z0-9-]+)"', index)
        candidates = [CLUB_SITE + p for p in dict.fromkeys(paths) if p.endswith(day.strftime('%d-%m-%Y'))]
    for url in candidates:
        page = fetch(url)
        for side in ('home', 'away'):
            team = re.search(r'class="rm-game__team rm-game__team--' + side + r'">\s*([^<]+)', page)
            if not team or normalized(team[1]) != normalized(match[side]):
                break
        else:
            album = AlbumPhotos()
            album.feed(page)
            if album.urls:
                return [{'url': u, 'caption': '皇马官方比赛图集', 'credit': 'Real Madrid', 'source': url}
                        for u in album.urls[:CLUB_PHOTO_LIMIT]]
    return []


def enrich_gallery(match, limit, fetch):
    entries = json.loads(Path(__file__).with_name('reviewed-media.json').read_text())
    selection = entries.get(match['id'], {}).get('madrid_gallery', {})
    try:
        official = club_photos(match, fetch, selection.get('club_report'))
    except (OSError, ValueError):
        official = []
    if official:
        match['club_album'] = official[0]['source']
    excluded = set(selection.get('exclude', []))
    cover_candidates = [p for p in match.get('photos', []) if p['url'] not in excluded]
    photos = []
    for photo in official + match.get('gallery', []):
        if photo['url'] not in excluded:
            photos.append(photo)
            excluded.add(photo['url'])
    match['gallery'] = photos[:limit]
    cover_urls = {p['url'] for p in cover_candidates}
    match['photos'] = (cover_candidates + [p for p in photos if p['url'] not in cover_urls])[:2]
