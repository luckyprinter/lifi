# Original Working Text Baseline

This folder preserves the early LiFi Arduino/ESP32 serial-monitor sketches from `.history/lifi_microcontroller`.

Use this as the simplest known working reference before the GUI, carousel transfer, FEC, and file-transfer protocol became more complex.

## Why This Baseline Matters

- The remembered stable test point was text transmission at up to `1000 Hz`.
- TX and RX both use the same timing formula:

```cpp
halfBitUs = 1000000UL / (2 * frequencyHz);
```

- At `1000 Hz`, `halfBitUs = 500 us`.
- Manchester encoding sends each bit as `!bit` then `bit`, MSB first.
- RX waits for a LOW-to-HIGH start transition, samples both Manchester halves, and treats the second half as the data bit.
- The receiver path is still digital `GPIO5`, not ADC threshold mode.

## Files

- `tx.ino`: original text-first transmitter, with a simple `SEND_IMAGE` mode that was not reliable enough for larger image work.
- `rx.ino`: matching digital Manchester receiver.

## Comparison Target

Compare later firmware against this folder when debugging:

- timing formula and default frequency
- bit polarity: TX sends `!bit` then `bit`; RX decodes from the second half
- RX sync edge: wait HIGH, wait LOW, then rising edge
- absence of carousel/FEC/preamble complexity
- direct serial monitor workflow without GUI framing
