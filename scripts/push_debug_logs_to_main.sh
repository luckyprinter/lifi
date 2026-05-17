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

git add -f debug_logs/.gitkeep debug_logs/*.log debug_logs/**/*.log 2>/dev/null || true

if git diff --cached --quiet -- debug_logs; then
  echo "No debug logs staged. Save TX/RX logs into debug_logs/ first."
  exit 0
fi

timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
git commit -m "Add LiFi debug logs - $timestamp"
git push origin main

echo "Debug logs pushed to origin/main."
