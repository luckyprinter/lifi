#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

branch="$(git symbolic-ref --short HEAD)"
if [[ "$branch" != "main" ]]; then
  echo "Refusing to push logs from branch '$branch'. Switch to main first:"
  echo "  git switch main"
  exit 1
fi

mkdir -p debug_logs

echo "Fetching latest origin/main..."
git fetch origin main

git add -f debug_logs/.gitkeep

while IFS= read -r -d '' log_file; do
  git add -f "$log_file"
done < <(find debug_logs -type f -name '*.log' -print0)

if ! git diff --cached --quiet -- debug_logs; then
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
  git commit -m "Add LiFi debug logs - $timestamp"
else
  echo "No new unstaged debug logs found."
fi

echo "Rebasing local main on origin/main before push..."
git pull --rebase --autostash origin main

ahead_count="$(git rev-list --count origin/main..HEAD)"
if [[ "$ahead_count" == "0" ]]; then
  echo "No local commits to push."
  exit 0
fi

git push origin main

echo "Pushed $ahead_count local commit(s) to origin/main."
