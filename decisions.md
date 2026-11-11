## 2026-11-05 — Trim Camoufox font groups and pin the claimed OS

- Context: The Docker image was 3.28GB on disk (1.51GB compressed); the Camoufox bundle was 2.54GB of it, and 2.1GB of that bundle was fonts for every spoofable OS.
- Decision: Pin `os='linux'` in the Camoufox launch kwargs and delete the macOS-only (`M`), macOS/Windows (`MW`) and Windows-only (`W`) font groups in the Docker build.
- Rationale: The browser now always claims Linux, so those groups are never read (`fonts/groups.json` → `readBy.lin`). The image drops from 3.28GB to 2.08GB on disk (fetch layer 2.54GB → 1.34GB), with no runtime download.
- Decided by: User.
- Consequences: Every request now presents a Linux fingerprint; the macOS and Windows font sets are gone, so a future decision to rotate the claimed OS must restore them (or stop deleting them).

## 2026-11-04 — Serialize release and publish workflow

- Context: Splitting release creation from image publishing left publishing outside the concurrency lock, and the current `origin/main` workflow also has a Dokploy deploy job.
- Decision: Rename the workflow to `release.yaml`, serialize the full workflow, use the release tag for the image, and run Dokploy deployment only after publish succeeds.
- Rationale: Prevent concurrent pushes from racing on `latest` and preserve deployment ordering and safeguards.
- Decided by: User.

## 2026-11-04 — Preserve pre-commit pre-push checks

- Context: Installing the main-branch guard could replace an existing pre-commit pre-push hook.
- Decision: Reject deletion of `main` and chain a recognized pre-commit hook after successful guard checks.
- Rationale: Keep both branch protection and existing pre-push checks active.
- Decided by: User.
- Consequences: Installation remains manual; the release workflow runs the shell regression suite before semantic-release.

## 2026-11-11 — Make the browser queue depth configurable

- Context: The waiting queue was fixed at 3 jobs, while `BROWSER_POOL_SIZE` was already configurable. A Dokploy deployment set `BROWSER_QUEUE_SIZE=12`; the pool ignored it and still rejected the seventh concurrent request with HTTP 503, because the value was a module constant.
- Decision: Read the queue depth from `BROWSER_QUEUE_SIZE` (default 3), validate it as a positive integer, and keep the constant as the code default.
- Rationale: Burst capacity needs both knobs together, and an env var that is silently ignored is worse than no env var.
- Decided by: User.
- Consequences: Waiting jobs cost no browser memory (a URL and a future), so a larger queue is cheap. Waiting time stays capped by `BROWSER_QUEUE_TIMEOUT_SECONDS = 30`; a request no worker starts within that window still gets HTTP 503.
