# Current Stable

This is the working baseline to use first.

## Physical Layer Preservation Note

Before changing firmware protocol, GUI behavior, FEC, carousel transfer, image,
audio, or video logic, read:

- `docs/current_working_physical_layer_baseline.md`
- `working_setup/README.md`

The current tested setup is:

```text
TX: ESP32 GPIO 5 -> 2N3904 -> IRF540N -> 12 V DC LED bulb
RX: BPW34 -> OPA2604 TIA -> LM393 comparator -> ESP32 RX input
```

Preserve the Manchester `halfBitUs` timing, RX sample point, comparator
polarity, and optical contrast before adding larger features.

## Easy GUI Launchers

- TX GUI: `Tx_gui.py`
- RX GUI: `Rx_gui.py`

Run:

```bash
python Tx_gui.py
python Rx_gui.py
```

## Preserved Working Copies

- TX firmware: `working_setup/firmware/tx/tx.ino`
- RX firmware: `working_setup/firmware/rx/rx.ino`
- TX GUI copy: `working_setup/gui/Tx_gui.py`
- RX GUI copy: `working_setup/gui/Rx_gui.py`

The original stable locations remain available:

- `firmware/stable/tx/tx.ino`
- `firmware/stable/rx/rx.ino`
- `apps/stable/Tx_gui.py`
- `apps/stable/Rx_gui.py`

## Firmware Notes

- Protocol: Manchester encoded frames
- Serial baud rate: `115200`
- Core timing: `halfBitUs = 1000000UL / (2 * frequencyHz)`
- First characterization frequencies: `500`, `1000`, `2000`, `4000`, `9000 Hz`

## Python Dependencies

The pinned dependency set in `requirements.txt` is current for this project:

- `customtkinter==5.2.2`
- `darkdetect==0.8.0`
- `packaging==26.0`
- `pillow==12.2.0`
- `pyserial==3.5`
- `crcmod==1.7`

Install with:

```bash
pip install -r requirements.txt
```

## Stability Rule

Do not promote a new image/audio/video/protocol feature until text transfer still
passes on the current physical layer and the test result is recorded in the
paper notes or debug logs.
