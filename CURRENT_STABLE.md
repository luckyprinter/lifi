# Current Stable

This is the working baseline to use first.

## Desktop App

- TX path: `apps/stable/Tx_gui.py`
- RX path: `apps/stable/Rx_gui.py`
- Purpose: carousel transfer GUI for text, image, audio, video, and files over the LiFi optical link
- Status: current stable
- Run TX:

```bash
python apps/stable/Tx_gui.py
```

- Run RX:

```bash
python apps/stable/Rx_gui.py
```

## Firmware

- TX: `firmware/stable/tx/tx.ino`
- RX: `firmware/stable/rx/rx.ino`
- Protocol: Manchester encoded carousel frames
- Serial baud rate: `115200`
- Default bit frequency: `9000 Hz`
- Runtime command: `FREQ=<hz>`
- RX debug command: `DEBUG=0` or `DEBUG=1`

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

## Stable Notes

- The stable app uses serial only for PC-to-board setup and local diagnostics.
- The actual LiFi transfer path is TX board to RX board through modulated light.
- WiFi, Bluetooth, and other wireless radio links are intentionally not part of this stable path.
- The GUI default frequency is aligned with the stable firmware default.
- File transfer is chunked, so 1 MB-class files are protocol-feasible. Expect long transfer times at low optical frequencies; use hardware tests to tune frequency, chunk size, rounds, and optical alignment.
