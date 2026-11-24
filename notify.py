"""Notify the repository owner using a GitHub issue, once per report day."""
import json
import os
from pathlib import Path
import urllib.request


def api(path, body=None, method=None):
    url = 'https://api.github.com/repos/' + os.environ['GITHUB_REPOSITORY'] + path
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
        method=method or ('POST' if body else 'GET'), headers={
            'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
            'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
            'User-Agent': 'FootballDaily'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    files = sorted(Path('docs/reports').glob('*.json'))
    if not files:
        raise RuntimeError('No report produced; cannot send completion notification')
    report = json.loads(files[-1].read_text())
    # A manual historical run must notify its own date, not the newest stored date.
    selected = os.environ.get('REPORT_DATE', '')
    if selected:
        report = json.loads(Path(f'docs/reports/{selected}.json').read_text())
    matches = report['matches']
    photos = sum(bool(m['photos']) for m in matches)
    clips = sum(bool(m['highlights']) for m in matches)
    missing = [f"{m['home']} vs {m['away']}：" + '、'.join(
        label for key, label in [('photos', '缺配图'), ('highlights', '缺官方集锦')]
        if not m[key]) for m in matches if not m['photos'] or not m['highlights']]
    status = '已生成，存在缺项' if report['errors'] or missing else '已生成'
    owner = os.environ['GITHUB_REPOSITORY'].split('/')[0]
    page = os.environ.get('PAGE_URL', '').rstrip('/')
    title = f"男足日报 {report['day']}"
    run_url = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    body = f"@{owner} 本期日报{status}。\n\n[查看图文报告]({page}/reports/{report['day']}.html) · [运行记录]({run_url})\n\n"
    body += f"已核实 {len(matches)} 场，{photos} 场有配图，{clips} 场有官方集锦。\n\n"
    body += '\n'.join('- ' + s for s in missing + report['errors'])
    body += '\n\n国家队和欧冠尚未接入独立赛程源，不能保证零漏报。图片为外链，可能受原站限制。'
    issues = api('/issues?state=all&per_page=100')
    previous = next((i for i in issues if i['title'] == title and 'pull_request' not in i), None)
    if previous:
        api(f"/issues/{previous['number']}", {'body': body}, 'PATCH')
    else:
        api('/issues', {'title': title, 'body': body, 'assignees': [owner]})


if __name__ == '__main__':
    main()
