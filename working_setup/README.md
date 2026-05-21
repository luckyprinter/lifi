# Working Setup

This folder is the preserved working LiFi implementation for the current thesis
baseline.

## Confirmed Physical Setup

TX:

```text
ESP32 GPIO 5 -> 2N3904 -> IRF540N -> 12 V DC LED bulb
```

RX:

```text
BPW34 photodiode -> OPA2604 TIA -> LM393 comparator -> ESP32 RX input
```

## Folder Map

- `firmware/tx/tx.ino` - transmitter firmware copy from the current stable tree.
- `firmware/rx/rx.ino` - receiver firmware copy from the current stable tree.
- `gui/Tx_gui.py` - transmitter GUI copy.
- `gui/Rx_gui.py` - receiver GUI copy.
- `gui/serial_utils.py` - shared serial helper for the GUI copies.

The root-level `Tx_gui.py` and `Rx_gui.py` files are launchers for quick access.

## Do Not Sidetrack Rule

Before changing image, audio, video, FEC, carousel behavior, or GUI automation,
verify that text transmission still works with the current physical layer.

Preserve these first:

- `halfBitUs = 1000000UL / (2 * frequencyHz)`
- receiver sampling near Manchester half-bit centers
- comparator polarity matching the RX firmware
- strong optical ON/OFF contrast
- CRC or another visible pass/fail result

See also:

- `docs/current_working_physical_layer_baseline.md`
- `paper/flowcharts.md`
