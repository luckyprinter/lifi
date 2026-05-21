# Original Working Text Baseline Analysis

Baseline files:

- `lifi_microcontroller/tx.ino`
- `lifi_microcontroller/rx.ino`
- Source recovered from `.history/lifi_microcontroller/*_20260509035213.ino`

## Key Timing

Both TX and RX use the same frequency-to-half-bit formula:

```cpp
halfBitUs = 1000000UL / (2 * frequencyHz);
```

At the remembered working test point:

- `frequencyHz = 1000`
- full Manchester bit period = `1000 us`
- half-bit period = `500 us`

This is much more forgiving than `9000 Hz`, where the half-bit is only about `55 us`.

## Original TX Behavior

- `TX_PIN = 8`
- serial monitor sends one text line
- each text character is transmitted directly as one Manchester byte
- MSB first
- each data bit is sent as:
  - first half = `!bit`
  - second half = `bit`

There is no GUI frame, no 32-byte preamble, no carousel transfer, no FEC, and no per-frame CRC in the text path.

## Original RX Behavior

- `RX_PIN = 5`
- digital input only
- waits for a LOW-to-HIGH transition:

```cpp
while (digitalRead(RX_PIN) == HIGH);
while (digitalRead(RX_PIN) == LOW);
```

- waits `halfBitUs / 2`
- samples two Manchester halves
- rejects a bit when both halves match
- decodes the second half as the data bit

## Debug Meaning

This baseline proves that the original stable behavior depended on:

- clean digital transitions at RX GPIO5
- matched TX/RX timing formula
- simple text bytes, not complex file framing
- Manchester polarity where the second half is the actual bit

For current debugging, compare every newer firmware against this baseline first:

- Does TX still generate the same optical Manchester polarity?
- Does the new MOSFET driver invert or preserve the GPIO waveform?
- Does LM393 output invert the optical signal?
- Is RX searching for the correct start edge?
- Is the RX input a real ESP32 logic HIGH/LOW at the selected frequency?

The most important thesis-relevant conclusion: if the physical receiver cannot deliver clean GPIO5 logic at 1 kHz, protocol changes cannot fix it. If 1 kHz works but 9 kHz fails, the bottleneck is likely front-end speed, threshold placement, or propagation delay.
