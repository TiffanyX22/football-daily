# Independent Google cloud timer

This timer does not depend on GitHub's scheduled-event service. It still uses GitHub-hosted runners to generate and send reports; runner outages can still delay delivery. A 5-minute Google clock trigger is a check interval, not a delivery guarantee.

1. Create a **private** standalone project in https://script.google.com/ using your personal Google account.
2. Copy `Code.gs` and `appsscript.json` from this folder into that project.
3. Create a fine-grained GitHub token limited to **TiffanyX22/football-daily**: **Actions: read/write**, **Contents: read**, with an appropriate expiration. No organization access or repository contents write is needed.
4. Store it as `GITHUB_TOKEN` in the project's **Script Properties**. Set `REPORT_EMAIL` to your own address for delayed-delivery alerts. Never paste the token into source code, a chat, or this public repository.
5. Run `installFootballTimer`, sign in and authorize the requested Google permissions. Confirm one `footballTick` clock trigger exists and inspect Executions for a successful check.

The timer checks the 16:00 Los Angeles cutoff, skips existing/ambiguous email reservations, avoids dispatching while a run is active, and backs off 10 minutes between dispatches. After 16:20 it sends at most one delayed-delivery notice per day if no accepted report is recorded. It also checks the Real Madrid men's schedule for undispatched completed matches. DST is handled using America/Los_Angeles.

Do not disable GitHub's fallback schedules until this independent trigger has been installed and verified. This repository folder alone does **not** install a Google trigger.
