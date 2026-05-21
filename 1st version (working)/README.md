# 1st Version (Working)

This folder preserves the first working LiFi microcontroller version as a safe reference point.

The files here are copied from the visible local `lifi_microcontroller` folder and should not be edited directly during new experiments. Make new experiments in separate folders so this remains a clean fallback.

## Included Files

- `lifi_microcontroller/tx.ino`
- `lifi_microcontroller/rx.ino`
- `lifi_microcontroller/README.md`
- `tx/tx.ino`
- `rx/rx.ino`

The `tx/` and `rx/` folders are Arduino IDE / Arduino CLI friendly copies. Arduino expects a sketch folder to contain an `.ino` file with the same name as the folder.

Important: `lifi_microcontroller/rx.ino` is the exact preserved copy. The Arduino-friendly `rx/rx.ino` only renames the global variable `index` to `byteIndex` because newer ESP32 Arduino cores already expose a C library function named `index()`.

## Known Behavior

- Default frequency: `1000 Hz`
- Shared timing formula:

```cpp
halfBitUs = 1000000UL / (2 * frequencyHz);
```

- At `1000 Hz`, `halfBitUs = 500 us`.
- TX uses Manchester encoding with `!bit` then `bit`.
- RX waits for the start transition, samples Manchester halves, and decodes the second half.
- This version is simple and useful as the control baseline before GUI/carousel/FEC changes.

## Note About `rx_file_transfer.ino`

The IDE currently shows `lifi_microcontroller/rx_file_transfer.ino`, but that file is not visible on disk from this repo checkout at the moment. Once it exists or is saved into this workspace, add a copy here so this folder exactly matches the local first working set.

## Compile Check

```bash
arduino-cli compile --fqbn esp32:esp32:esp32doit-devkit-v1 "1st version (working)/tx"
arduino-cli compile --fqbn esp32:esp32:esp32doit-devkit-v1 "1st version (working)/rx"
```
