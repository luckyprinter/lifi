# Current Working Physical Layer Baseline

Date recorded: 2026-05-22

This note preserves the currently tested working LiFi setup so future firmware,
GUI, and protocol work does not drift away from the physical layer that is known
to work.

## Tested Working Circuit

TX path:

```text
ESP32 GPIO 5 -> 2N3904 -> IRF540N -> 12 V DC LED bulb
```

RX path:

```text
BPW34 photodiode -> OPA2604 transimpedance amplifier -> LM393 comparator -> ESP32 RX input
```

This circuit is the current known-good baseline. Any future change to MOSFET
driver topology, comparator polarity, threshold, photodiode bias, receiver pin,
or encoding should be treated as a new experiment until proven working again.

## Core Timing Rule

The TX and RX meet at the Manchester half-bit timing:

```cpp
halfBitUs = 1000000UL / (2 * frequencyHz);
```

Examples:

```text
500 Hz  -> halfBitUs = 1000 us
1000 Hz -> halfBitUs = 500 us
2000 Hz -> halfBitUs = 250 us
4000 Hz -> halfBitUs = 125 us
9000 Hz -> halfBitUs = 55 us
```

This timing is the middle point of the system. The transmitter must change the
LED state at each half-bit boundary, and the receiver must sample near the
center of each Manchester half-bit. If either side changes this relationship,
the receiver may still see voltage transitions but fail sync or CRC.

## Receiver Sampling Hint

The receiver should:

1. Lock to the expected start transition.
2. Wait about `halfBitUs / 2`.
3. For each data bit, sample once per half-bit.
4. Reject or count a bit as unstable when both Manchester halves read the same.

The useful decoded bit is the second Manchester half in the current firmware
style. Keep this mapping stable unless the TX encoding polarity is intentionally
changed and tested.

## Polarity Warning

The BPW34 + OPA2604 + LM393 receiver produces a comparator logic waveform. The
ESP32 firmware must match that comparator polarity.

Do not blindly normalize "light = HIGH" or "light = LOW". Check the actual LM393
output:

```text
LED bright / light present -> comparator output = ?
LED dim/off / less light   -> comparator output = ?
```

Then make the RX start-transition logic and Manchester bit mapping match the
measured output.

For LM393 output, prefer using an ESP32 digital GPIO input. ADC threshold mode is
mainly for direct analog sensor testing or when the comparator stage is bypassed.

## Do Not Sidetrack This Baseline

Before changing protocol complexity, preserve these first:

- deterministic integer timing using `halfBitUs`
- direct Manchester half-bit transitions
- correct TX/RX polarity
- strong optical contrast
- enough preamble or start pattern for RX lock
- CRC or another visible success/failure check

Avoid jumping straight to FEC, carousel changes, PWM dimming, image transfer,
audio, or video until text transfer is characterized again on this exact circuit.

## Recommended Characterization Path

Text first:

- Test `500 Hz`, `1000 Hz`, `2000 Hz`, `4000 Hz`, and `9000 Hz`.
- Record received text, CRC pass/fail, bad/unstable bit counts, comparator
  threshold, and observed voltage behavior.
- Use short payloads first, then gradually increase message length.

Image next:

- Start with small grayscale or tiny RGB files.
- Use small chunks such as `32` or `64` bytes.
- Keep CRC per chunk.
- Add retry or carousel only after raw chunk reception is stable.

Audio later:

- Start with stored audio files, not live microphone streaming.
- Try tones first, then short low-bitrate samples.
- Consider 8-bit PCM only for very slow tests; ADPCM is a better next step if
  text and image chunks are reliable.

Video last:

- Real video is likely too much for this low-cost optical link at the current
  tested rates.
- A practical thesis demo is slow image sequence transfer or very tiny grayscale
  frames, not real-time video.

## Future Codex / Collaborator Reminder

If the project gets sidetracked again, return to this baseline and ask:

```text
Are TX half-bit timing, RX sample timing, comparator polarity, and optical
contrast still the same as the known-good setup?
```

If the answer is no, debug the physical layer first before changing the protocol.
