# LiFi Project

This repo is arranged so the working version is easy to find and older experiments stay available.

## Stable Version

Use these first when you want the current working text-based LiFi setup:

- GUI: `apps/stable/lifi_gui.py`
- Transmitter firmware: `firmware/stable/tx/tx.ino`
- Receiver firmware: `firmware/stable/rx/rx.ino`

The stable firmware uses Manchester encoding with configurable frequency commands from the GUI.

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
  - `esp32_tx/` - ESP32 transmitter prototype

Each Arduino sketch has its own folder so the Arduino IDE can open it cleanly.

## Samples

Received image outputs are stored in:

- `samples/received_images/`

## Running the Stable GUI

```bash
python apps/stable/lifi_gui.py
```

Install Python dependencies first if needed:

```bash
pip install -r requirements.txt
```
