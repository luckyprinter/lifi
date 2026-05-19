#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT_DIR"

echo "Starting LiFi Packet CRC test GUI..."
echo "Default ports: RX=/dev/ttyUSB0, TX=/dev/ttyUSB1"
"$PYTHON_BIN" apps/experiments/packet_crc_gui.py
