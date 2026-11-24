# 每日男足图文日报

个人使用的免费模板型程序：Python、Pillow、GitHub Actions 标准 Linux runner、GitHub Pages。不使用 TinyFish、付费 AI 或 API 密钥。

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

需要 Python 3.11+、网络和中文字体（Linux 安装 `fonts-noto-cjk`；macOS 自动使用系统中文字体）：

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python agent.py --date 2026-11-23
```

输出 `docs/index.html` 和 `docs/reports/YYYY-MM-DD.{html,json}`。可用 Actions → Daily men's football → Run workflow 手动补刊。

## 社媒图文图片

每场自动输出一张 1080px 宽的 PNG，图片高度随内容调整，包含比赛配图、比分、关键时刻、积分影响及官方集锦二维码；缺图时显示缺项。网页支持单张下载和整期 ZIP 下载，邮件通知附 ZIP 链接。文件位于 `docs/posters/YYYY-MM-DD/`。

## 部署

仅部署到个人账号 `TiffanyX22/football-daily`。仓库公开只包含本项目；不要上传工作目录其他内容或凭证。Pages source 设为 GitHub Actions。工作流仅使用标准 Ubuntu runner，Pages artifact 保留一天，无额外付费服务。

ESPN 公开网页接口没有稳定性承诺，可能修改或限制访问。网页照片外链展示；社媒图片按用户要求合成配图并保留来源归属，照片版权仍归原作者。历史报告存在仓库中；需自行遵守数据及媒体来源的使用条件。

旧 ChatGPT 云端任务不会由此程序自动停用；新部署验证后可另行关闭，避免重复通知。

## 邮件正文预览与附件

`mail_report.py` 使用 Gmail SSL SMTP，邮件正文嵌入小预览，同时直接附上全部原尺寸 PNG 和 ZIP。内容多时按安全大小分封，附件不是网页链接。

在本仓库 Actions Secrets 中配置 `SMTP_USERNAME`、`SMTP_PASSWORD`（Google 应用专用密码，不能用普通登录密码）、`REPORT_EMAIL`。三个 Secret 齐备后自动改发附件邮件，并停止重复的 GitHub Issue 邮件。未配置时继续原来的 GitHub 通知，不冒充已开通附件邮件。

Gmail 应用专用密码由用户在 Google 安全页面创建并直接填入 GitHub Secrets，不进入代码、聊天、运行日志或仓库。需要 Google 两步验证，部分账号政策可能不提供应用密码。

本地不发送邮件的 MIME 验证：`python mail_report.py --date 2026-11-23 --dry-run /tmp/football-email-preview`。不要提交 `.eml` 或授权凭证。

每日额外生成本期赛事的完整积分榜 PNG（排名、积分、场次、净胜球，标出本期参赛球队），与比赛图片一起附在邮件和 ZIP 中。积分为抓取时快照；无积分表的友谊赛不生成积分图。

积分图使用中英双语队名与数据源提供的真实队标；中文名在上、英文名在下。中文译名维护在 team-names.json，缺失名称或队标会明确记录为资料缺项。

关键事件保留球员英文名，并补充中文名及本场名单中的球衣号码；仅在进球事件文字明确记录 Assisted by 时列助攻，未记录则标明“数据源未记录”。中文译名按球员 ID 维护在 player-names.json，缺失不猜填。

所有新图片统一为1080×1312竖版：每日双语赛果封面、比赛特辑分页、每页7队的双语积分榜。邮件及ZIP只包含本期新尺寸图片。点球进球不显示助攻行。
