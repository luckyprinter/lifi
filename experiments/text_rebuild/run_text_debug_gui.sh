#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 experiments/text_rebuild/gui/lifi_text_debug_gui.py
