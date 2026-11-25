"""Static per-match photo gallery page (比赛图集) for GitHub Pages.

Only photos already verified for this exact event (ESPN recap tied to the event
ID, UEFA live-blog photos published between kickoff and full time) are listed.
Images are hot-linked from the original publisher with credit and source; they
are not copied into the repository.
"""
from agent import esc


def render_gallery(match, day, report_url):
    photos = match.get('gallery') or match.get('photos') or []
    title = f"{match['home']} {match['score']} {match['away']}"
    parts = [f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>比赛图集 · {esc(title)}</title><style>
body{{margin:0;background:#101715;color:#edf5ed;font:17px/1.6 system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:28px 18px}}a{{color:#a8e5ba}}
h1{{font-size:34px;line-height:1.25;margin:6px 0}}.eyebrow{{color:#a4cc70;letter-spacing:3px;margin:0}}.muted,figcaption{{color:#a8b8ac;font-size:14px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px;margin-top:24px}}figure{{margin:0;background:#18231f;border-radius:12px;overflow:hidden}}
figure a.full{{display:block}}img{{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;background:#22302a}}figcaption{{padding:10px 12px}}.missing{{padding:12px 16px;background:#302b20;border-radius:8px;color:#edd9aa}}
</style><main><p class="eyebrow">{esc(match['league'])} · PHOTO GALLERY / 比赛图集</p><h1>{esc(title)}</h1>
<p class="muted">{esc(day)} · 洛杉矶开球 {esc(match['kickoff'][:16].replace('T', ' '))} · 共 {len(photos)} 张本场照片 · 点图看原图</p>
<p><a href="{esc(report_url)}">← 返回本场图文战报</a>''']
    for clip in match.get('highlights', [])[:1]:
        parts.append(f' · <a href="{esc(clip["url"])}">官方视频集锦</a>')
    parts.append('</p>')
    if not photos:
        parts.append('<p class="missing">本场暂未取得可核实的比赛照片；不使用其他比赛或资料图替代。</p>')
    parts.append('<div class="grid">')
    for index, p in enumerate(photos, 1):
        parts.append(f'<figure><a class="full" href="{esc(p["url"])}" target="_blank" rel="noopener">'
                     f'<img loading="lazy" src="{esc(p["url"])}" alt="{esc(p.get("caption", ""))}" referrerpolicy="no-referrer" '
                     f'onerror="this.hidden=true"></a><figcaption>{index}. {esc(p.get("caption", ""))}<br>'
                     f'© {esc(p.get("credit", "原作者"))} · <a href="{esc(p.get("source", p["url"]))}">来源</a></figcaption></figure>')
    parts.append('</div><p class="muted">照片版权归原摄影师及发布方；本页仅外链原站公开图片，不做转存。</p></main></html>')
    return ''.join(parts)
