#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 lifi_microcontroller/text_rebuild_debug/gui/lifi_text_debug_gui.py
