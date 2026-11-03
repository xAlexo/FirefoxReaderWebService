## 2026-11-04 — Serialize release and publish workflow

- Context: Splitting release creation from image publishing left publishing outside the concurrency lock, and the current `origin/main` workflow also has a Dokploy deploy job.
- Decision: Rename the workflow to `release.yaml`, serialize the full workflow, use the release tag for the image, and run Dokploy deployment only after publish succeeds.
- Rationale: Prevent concurrent pushes from racing on `latest` and preserve deployment ordering and safeguards.
- Decided by: User.
