#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT_DIR"

echo "Starting LiFi RX GUI on the baseline experiment branch..."
"$PYTHON_BIN" apps/stable/Rx_gui.py &
RX_PID=$!

sleep 1

echo "Starting LiFi TX GUI on the baseline experiment branch..."
"$PYTHON_BIN" apps/stable/Tx_gui.py &
TX_PID=$!

echo
echo "RX GUI PID: $RX_PID"
echo "TX GUI PID: $TX_PID"
echo "Default ports: RX=/dev/ttyUSB0, TX=/dev/ttyUSB1"
echo "Close both GUI windows to end the test."

wait "$RX_PID" "$TX_PID"
