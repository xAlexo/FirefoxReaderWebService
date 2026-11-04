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
