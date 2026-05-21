# Current Stable

This is the working baseline to use first.

## Physical Layer Preservation Note

Before changing firmware protocol, GUI behavior, FEC, carousel transfer, image,
audio, or video logic, read:

- `docs/current_working_physical_layer_baseline.md`

That note records the currently tested working physical setup:
`2N3904 + IRF540N` TX and `BPW34 + OPA2604 + LM393` RX. Preserve the
Manchester `halfBitUs` timing, RX sample point, comparator polarity, and optical
contrast before adding larger features.

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
- Runtime commands: `FREQ=<hz>`, `TXMODE=OOK`, `TXMODE=PWM`, `QUIET=0/1`, `LEDTEST`
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
- The stable TX optical mode is `ON/OFF` for the current IRLZ44N + TEPT4400 hardware. DC-biased PWM is still available from the TX GUI for experiments, but it is not the default because the simple receiver may decode it less reliably.
- File transfer is chunked, so 1 MB-class files are protocol-feasible. Expect long transfer times at low optical frequencies; use hardware tests to tune frequency, chunk size, rounds, and optical alignment.

## Current Hardware Baseline

- TX pin: ESP32 `GPIO 5`
- TX driver: `GPIO 5 -> 220 ohm -> IRLZ44N gate`, `10k` gate pulldown to GND, source to GND, drain to LED negative, LED positive to +12 V
- TX polarity: active-high, configured as `LED_ACTIVE_LOW = false`
- RX pin: ESP32 `GPIO 5`
- RX sensor: TEPT4400 with a load resistor from 3.3 V to the GPIO input node
- RX resistor starting point: `10k`; try `22k` or `47k` for more distance, but expect slower edges and more ambient-light sensitivity
