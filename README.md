# LiFi Project

This repo is arranged so the working version is easy to find and older experiments stay available.

- Current stable details: `CURRENT_STABLE.md`
- Experimental inventory: `EXPERIMENTAL.md`

## Stable Version

Use these first when you want the current working carousel-based LiFi setup:

- TX GUI: `apps/stable/Tx_gui.py`
- RX GUI: `apps/stable/Rx_gui.py`
- Transmitter firmware: `firmware/stable/tx/tx.ino`
- Receiver firmware: `firmware/stable/rx/rx.ino`

The stable firmware uses Manchester encoding with configurable frequency commands from the GUI. The current stable default is `9000 Hz`.

Serial is used only for setup, local control, and diagnostics between the PC and microcontrollers. The actual data link remains LiFi: TX emits modulated light and RX decodes that light.

## Experiments

Experimental or older versions are kept here:

- `apps/experiments/`
  - `basic_tk_gui.py` - simple early Tkinter GUI
  - `lifi_gui_sim.py` - simulator mode
  - `file_transfer_gui.py` - file/image transfer GUI
  - `file_transfer_serial.py` - command-line file transfer helper
  - `gui_test_file_transfer.py` - earlier file transfer GUI test
- `firmware/experiments/`
  - `original_tx/` and `original_rx/` - first Manchester sketches
  - `packet_tx/` and `packet_rx/` - packet/CRC prototype
  - `file_transfer_tx/` and `file_transfer_rx/` - file transfer prototype
  - `file_transfer_v1_legacy/` - older file-transfer sketches
  - `esp32_tx/` - ESP32 transmitter prototype

Each Arduino sketch has its own folder so the Arduino IDE can open it cleanly.

## Samples

Received image outputs are stored in:

- `samples/received_images/`

## Running the Stable GUI

```bash
python apps/stable/Tx_gui.py
python apps/stable/Rx_gui.py
```

Install Python dependencies first if needed:

```bash
pip install -r requirements.txt
```

## Serial Connection Setup

The GUI talks to each ESP32 over USB serial. This serial cable is only for local control and diagnostics; the actual data path remains one-way optical LiFi.

### Linux

Most ESP32 boards appear as `/dev/ttyUSB0` or `/dev/ttyACM0`. If the GUI shows `Permission denied`, do not run the GUI as root for normal use. Add your user to the serial group instead.

First check the group that owns the port:

```bash
ls -l /dev/ttyUSB0
```

If the group is `dialout`, use:

```bash
sudo usermod -aG dialout $USER
```

If the group is `uucp`, which is common on some Linux installs, use:

```bash
sudo usermod -aG uucp $USER
```

Then log out and back in, or reboot. You can also try `newgrp dialout` or `newgrp uucp` for the current terminal session, but a full logout is the most reliable. Confirm group membership with:

```bash
groups
```

For a temporary one-session test only:

```bash
sudo chmod a+rw /dev/ttyUSB0
```

Replace `/dev/ttyUSB0` with the port shown by the GUI if needed.

### Windows

ESP32 boards usually appear as `COM3`, `COM4`, etc. If Windows reports access denied, close Arduino IDE Serial Monitor, VS Code serial monitor, PuTTY, or any other program using the same COM port. If the port does not appear, install the board driver for your USB bridge, commonly CP210x or CH340.

### GUI Port Buttons

- `Refresh`: rescans likely physical USB serial ports. The dropdown favors ESP32-style devices such as CP210x, CH340, FTDI, `/dev/ttyUSB*`, `/dev/ttyACM*`, and Windows `COM*` ports.
- `Connect`: connects to the port currently selected in the dropdown.
- `Set Freq`: sends the optical Manchester frequency to the connected ESP32.
- `Clear Log`: clears the visible event log only. It does not reset firmware or transfer state.

## TX GUI Options

- `Optical frequency`: Manchester bit frequency used by the light link. The default is `9000 Hz` because this project has been stable around 5-9 kHz. Higher values can improve throughput but may reduce reliability on the current LED/phototransistor hardware.
- `Chunk bytes`: file payload bytes per optical chunk. Smaller chunks, such as `256`, are more reliable because a corrupted frame loses less data and has a shorter on-air time. Larger chunks, such as `1024` or `2048`, reduce header overhead and can improve throughput, but they are more likely to fail CRC on noisy or poorly aligned hardware.
- `Carousel rounds`: how many times the TX sends the full chunk sequence. More rounds improve the chance that RX eventually receives every chunk, but increase transfer time and visible packet-envelope flicker. The default is `2` because parity FEC now helps recover isolated missing chunks.
- `Round gap ms`: pause between carousel rounds. A lower value reduces total delay and visible brightness pulsing. If the RX misses many final chunks, increase this slightly.
- `FEC`: enables XOR parity recovery. One parity frame is sent per group of 8 data chunks. RX can recover exactly one missing chunk in that group. If two or more chunks are missing in the same group, RX waits for another carousel round.
- `Theme`: visual theme only. The default is the cleaner Light theme.
- `Image`, `Audio`, `Video`: send those file categories through the same LiFi chunk protocol. The generic file picker is intentionally hidden to keep demo workflows focused.

## RX GUI Options

- `Optical frequency`: must match the TX frequency.
- `RX Debug`: prints Manchester instability warnings from the RX firmware. Keep it off for normal transfers because extra serial output can make logs noisy.
- `Receive folder`: folder where received files are saved. Text transfers are also shown in the text panel.
- `Reset Transfers`: clears the RX GUI's current chunk/parity buffers. Use this before starting a fresh test if a previous transfer was stopped halfway.
- `Open Folder` / `Open Last`: convenience buttons for checking received files.
- `Clear Log`: clears the visible event log without deleting received text or saved files.

## Reliability Tuning Notes

Start thesis demos with:

- Frequency: `9000 Hz`
- Chunk bytes: `512`
- Carousel rounds: `2`
- Round gap: `250 ms`
- FEC: enabled

If transfers fail CRC often, try this order:

1. Improve LED-to-phototransistor alignment and reduce ambient light.
2. Lower frequency to `7000 Hz`.
3. Lower chunk size to `256`.
4. Increase carousel rounds to `3`.
5. Increase round gap to `400-500 ms` only if final chunks are consistently missed.
