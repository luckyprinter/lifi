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
