# 每日男足图文日报

个人使用的免费模板型程序：Python 标准库、GitHub Actions 标准 Linux runner、GitHub Pages。不使用 TinyFish、付费 AI 或 API 密钥。

每天计划于 **America/Los_Angeles 16:00** 运行，自动随夏令时调整。GitHub 免费调度可能延迟或丢弃任务，不能承诺准点。成功发布后给仓库所有者创建 GitHub Issue 通知；是否推送邮件/手机由个人 GitHub 设置决定。

## 覆盖与验收

- 男足五大联赛、欧冠、成年国家队主要正赛/预选赛/友谊赛。实际代码中的 ESPN competition allowlist 见 `LEAGUES`；未提供数据的赛事不保证覆盖。
- 以每日报告日 16:00 为固定截稿，按**实际终场事件时间**归档；没有终场时间的 FT 记录列为错误，绝不用开球时间猜终场。
- ESPN 赛果、关键事件、积分表。Soccerbase 五大联赛当日赛果作独立单向核对，发现遗漏/比分冲突显示并使 CI 失败。队名别名未识别也可能产生告警。国家队和欧冠尚无独立源保证完整。
- 照片仅取明确关联该 event ID 的 recap；不会使用联赛新闻栏的无关照片。每次验证 Content-Type。官方视频封面明确标注封面，不冒充额外现场照。
- `reviewed-media.json` 是人工复核过的三场历史媒体入口，用来验证 2026-11-23 的样刊；它不是未来日期的媒体数据源。日常官方视频自动发现需要公开搜索可用，检索失败会显示缺项。
- 官方视频发现只接受白名单域名、日期和视频页面证据。不绕过登录/反爬，不伪造 URL。部分比赛会缺图、缺集锦；本项目不能保证所有场次全部媒体齐全。
- 积分表是抓取时的快照，历史补刊不冒充当时排名；不编造名次升降。杯赛晋级尚未自动推导。

## 本地运行

需要 Python 3.11+ 和网络，无需安装依赖：

```sh
python -m unittest discover -s tests -v
python agent.py --date 2026-11-23
```

输出 `docs/index.html` 和 `docs/reports/YYYY-MM-DD.{html,json}`。可用 Actions → Daily men's football → Run workflow 手动补刊。

## 部署

仅部署到个人账号 `shuyaox/football-daily`。仓库公开只包含本项目；不要上传工作目录其他内容或凭证。Pages source 设为 GitHub Actions。工作流仅使用标准 Ubuntu runner，Pages artifact 保留一天，无额外付费服务。

ESPN 公开网页接口没有稳定性承诺，可能修改或限制访问。照片仅外链展示并标注原始来源/版权，不下载再分发。历史报告存在仓库中；需自行遵守数据及媒体来源的使用条件。

旧 ChatGPT 云端任务不会由此程序自动停用；新部署验证后可另行关闭，避免重复通知。
