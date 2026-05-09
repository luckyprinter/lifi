# Experimental Work

These files are kept for testing, recovery, and future development. They are not the current stable baseline.

## Experimental Apps

- `apps/experiments/basic_tk_gui.py` - early Tkinter text GUI
- `apps/experiments/lifi_gui_sim.py` - simulator-style GUI
- `apps/experiments/file_transfer_gui.py` - file and image transfer GUI prototype
- `apps/experiments/file_transfer_serial.py` - command-line file transfer helper
- `apps/experiments/gui_test_file_transfer.py` - earlier file transfer GUI test

## Experimental Firmware

- `firmware/experiments/original_tx/` - first Manchester TX sketch
- `firmware/experiments/original_rx/` - first Manchester RX sketch
- `firmware/experiments/packet_tx/` - packet and CRC TX prototype
- `firmware/experiments/packet_rx/` - packet and CRC RX prototype
- `firmware/experiments/file_transfer_tx/` - file transfer TX prototype
- `firmware/experiments/file_transfer_rx/` - file transfer RX prototype
- `firmware/experiments/file_transfer_v1_legacy/` - older top-level file-transfer sketches moved from `lifi_microcontroller/`
- `firmware/experiments/esp32_tx/` - ESP32 transmitter prototype
- `firmware/experiments/dc_biased_pwm_tx/` - ESP32 TX experiment using 50 kHz DC-biased PWM Manchester modulation to reduce visible brightness fluctuation

## Promotion Rule

Move an experiment to stable only after:

1. TX and RX sketches compile in the Arduino IDE.
2. The matching desktop app runs without Python syntax errors.
3. Text transfer still works after the change.
4. Any new feature, such as file transfer, is verified on hardware.
