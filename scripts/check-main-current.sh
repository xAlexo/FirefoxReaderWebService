#!/usr/bin/env bash
set -euo pipefail

[[ ${PRE_COMMIT_REMOTE_NAME:-} == origin ]] || exit 0

local_branch=${PRE_COMMIT_LOCAL_BRANCH:-}
case "$local_branch" in
  refs/heads/*) ;;
  "") echo "Cannot identify the branch being pushed; refusing push." >&2; exit 1 ;;
  *) exit 0 ;;
esac

pushed_sha=${PRE_COMMIT_TO_REF:-}
if [[ -z "$pushed_sha" ]]; then
  echo "Cannot identify the pushed commit; refusing push." >&2
  exit 1
fi

git fetch --quiet origin +refs/heads/main:refs/remotes/origin/main

if git merge-base --is-ancestor origin/main "$pushed_sha"; then
  exit 0
fi

printf 'Push blocked: %s does not contain the latest origin/main (%s). Merge or rebase origin/main, then retry.\n' \
  "${local_branch#refs/heads/}" "$(git rev-parse --short origin/main)" >&2
exit 1
