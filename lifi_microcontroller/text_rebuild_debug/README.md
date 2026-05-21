# LiFi Text Rebuild Experiment

This folder is the clean restart point based on the original Arduino serial-monitor era.

Goal: recover a reliable text-only LiFi link first, then add GUI control, packet checks, higher frequency, and later file transfer one step at a time.

## Why This Exists

The original working path was simple:

- one text byte at a time
- Manchester `!bit` then `bit`
- shared timing formula:

```cpp
halfBitUs = 1000000UL / (2 * frequencyHz);
```

- RX digital input on GPIO5
- no carousel, FEC, large chunks, or GUI binary framing

This experiment keeps that timing model but adds debug observability.

## Folder Layout

- `firmware/tx_text_debug/tx_text_debug.ino`: TX firmware for text packets and raw Manchester test bytes.
- `firmware/rx_text_debug/rx_text_debug.ino`: RX firmware with bit/byte/packet debug output.
- `gui/lifi_text_debug_gui.py`: single desktop GUI for TX and RX serial ports.
- `logs/`: default experiment log folder.

## GUI Direction

For now the GUI uses Python `tkinter` + `ttk` because it is built into Python, easy to debug, and works on Linux/Windows.

Packaging target later:

- Linux runnable: PyInstaller one-folder build.
- Windows `.exe`: PyInstaller one-file or one-folder build.

If the UI grows into a polished thesis/demo tool, the best upgrade path is PySide6/Qt because it packages well and gives better custom widgets. For debugging the firmware right now, `tkinter` is faster and lower risk.

## Firmware Protocol

Default frequency: `1000 Hz`.

Manchester bit:

- first half = `!bit`
- second half = `bit`
- RX decodes the second half

Text packet sent optically:

```text
PREAMBLE 0x55 repeated
START    0x02
TYPE     0x01 for text
LEN_MSB
LEN_LSB
PAYLOAD bytes
CRC_MSB  CRC16-CCITT over TYPE/LEN/PAYLOAD
CRC_LSB
STOP     0x03
```

RX prints human-readable debug lines such as:

```text
RX_BIT:1
RX_BYTE:0x55:01010101
RX_PACKET_OK:type=1:len=5:crc=0x1234:text=hello
RX_PACKET_FAIL:crc expected=0x1234 got=0x5678
RX_PACKET_INCOMPLETE:timeout
```

## Suggested First Test

1. Upload `rx_text_debug.ino` to RX ESP32 on `/dev/ttyUSB0`.
2. Upload `tx_text_debug.ino` to TX ESP32 on the other USB port.
3. Run:

```bash
python3 experiments/text_rebuild/gui/lifi_text_debug_gui.py
```

4. Connect RX and TX.
5. Set frequency to `1000`.
6. Send `hello`.
7. Watch:
   - live RX bits
   - RX bytes
   - packet status
   - CRC result

Only increase frequency after `1000 Hz` is repeatedly clean.

## Arduino CLI Commands

Compile:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32doit-devkit-v1 lifi_microcontroller/text_rebuild_debug/firmware/rx_text_debug
arduino-cli compile --fqbn esp32:esp32:esp32doit-devkit-v1 lifi_microcontroller/text_rebuild_debug/firmware/tx_text_debug
```

Upload, assuming RX is `/dev/ttyUSB0` and TX is `/dev/ttyUSB1`:

```bash
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32doit-devkit-v1 lifi_microcontroller/text_rebuild_debug/firmware/rx_text_debug
arduino-cli upload -p /dev/ttyUSB1 --fqbn esp32:esp32:esp32doit-devkit-v1 lifi_microcontroller/text_rebuild_debug/firmware/tx_text_debug
```

If your board is not DOIT ESP32 DEVKIT V1, change the FQBN to the one shown by:

```bash
arduino-cli board listall esp32
```

## GUI Run Command

```bash
./lifi_microcontroller/text_rebuild_debug/run_text_debug_gui.sh
```

Or directly:

```bash
python3 lifi_microcontroller/text_rebuild_debug/gui/lifi_text_debug_gui.py
```
