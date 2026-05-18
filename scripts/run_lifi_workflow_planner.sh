#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/web/lifi-workflow-planner"

cd "$APP_DIR"

echo "Starting LiFi Workflow Planner..."
echo "Local URL will be: http://localhost:5174/"
echo

if [ ! -d "node_modules" ]; then
  npm install
fi

npm run app
