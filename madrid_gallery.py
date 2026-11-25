"""Match-specific selections and official first-team photo albums."""
import datetime as dt
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from agent import normalized

CLUB_SITE = 'https://www.realmadrid.com'
REPORT_PATH = '/en-US/news/football/first-team/reports/'


def club_report(match, fetch):
    day = dt.datetime.fromisoformat(match['kickoff']).astimezone(ZoneInfo('Europe/Madrid'))
    index = fetch(CLUB_SITE + '/en-US/football/first-team/home')
    for path in dict.fromkeys(re.findall(r'href="(' + REPORT_PATH + r'[a-zA-Z0-9-]+)"', index)):
        if not path.endswith(day.strftime('%d-%m-%Y')):
            continue
        url = CLUB_SITE + path
        page = fetch(url)
        for side in ('home', 'away'):
            team = re.search(r'class="rm-game__team rm-game__team--' + side + r'">\s*([^<]+)', page)
            if not team or normalized(team[1]) != normalized(match[side]):
                break
        else:
            if re.search(r'https://assets\.realmadrid\.com/is/image/realmadrid/\d{3}_', page):
                return url
    return None


def enrich_gallery(match, limit, fetch):
    entries = json.loads(Path(__file__).with_name('reviewed-media.json').read_text())
    selection = entries.get(match['id'], {}).get('madrid_gallery', {})
    album = selection.get('club_report')
    if not album:
        try:
            album = club_report(match, fetch)
        except (OSError, ValueError):
            pass
    if album:
        match['club_album'] = album
    if selection.get('instagram_post'):
        match['instagram_post'] = selection['instagram_post']
    excluded = set(selection.get('exclude', []))
    cover_candidates = [p for p in match.get('photos', []) if p['url'] not in excluded]
    photos = []
    for photo in selection.get('photos', []) + match.get('gallery', []):
        if photo['url'] not in excluded:
            photos.append(photo)
            excluded.add(photo['url'])
    match['gallery'] = photos[:limit]
    cover_urls = {p['url'] for p in cover_candidates}
    match['photos'] = (cover_candidates + [p for p in photos if p['url'] not in cover_urls])[:2]
