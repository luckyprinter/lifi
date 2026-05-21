# LiFi Text Debug GUI Control Guide

This guide explains the controls in `gui/lifi_text_debug_gui.py`.

## Frequency Behavior

The GUI can set the same frequency on both TX and RX.

Use the `Freq` field, then click:

```text
Set Both
```

That sends this command to both connected boards:

```text
FREQ=<value>
```

Example:

```text
FREQ=1000
```

Both TX and RX firmware then compute:

```cpp
halfBitUs = 1000000UL / (2 * frequencyHz);
```

At `1000 Hz`:

```text
halfBitUs = 500 us
full Manchester bit = 1000 us
```

## RX / Receiver Controls

`Port`

Selects the RX ESP32 serial port. The expected default is usually:

```text
/dev/ttyUSB0
```

`Connect`

Opens or closes the RX serial connection.

`Refresh`

Scans USB serial ports again.

`Invert RX`

Sends:

```text
INV=0
```

or:

```text
INV=1
```

Use this when the receiver signal polarity is inverted. This is especially important when using an LM393 comparator or a phototransistor circuit where light and dark may be reversed.

`Bits`

Turns live bit debug on or off.

When enabled, RX prints lines like:

```text
RX_BIT:1
RX_BIT:0
```

The GUI displays these in `Live RX Bits`.

`Bytes`

Turns live byte debug on or off.

When enabled, RX prints lines like:

```text
RX_BYTE:0x55:01010101
```

The GUI displays these in `Decoded RX Bytes`.

`RXCAP 1s`

Samples the RX logic level for one second.

It reports:

- number of samples
- high count
- low count
- transition count
- a short binary sample string

This is useful before sending real text. If RXCAP shows no transitions, the receiver is not seeing the optical signal correctly.

`Stats`

Requests RX counters:

- bits received
- bytes received
- unstable Manchester bits
- successful packets
- failed packets

`Reset`

Clears the GUI RX displays and sends:

```text
RESET
```

to the RX firmware.

## TX / Transmitter Controls

`Port`

Selects the TX ESP32 serial port. The expected default is usually the other USB port, for example:

```text
/dev/ttyUSB1
```

`Connect`

Opens or closes the TX serial connection.

`Invert TX`

Sends:

```text
INV=0
```

or:

```text
INV=1
```

Use this when the TX driver inverts the ESP32 GPIO. For example, a 2N3904 inverter stage can make GPIO LOW turn the LED ON.

`Freq`

The desired Manchester frequency in Hz.

Start with:

```text
1000
```

Only increase frequency after the link is clean.

`Set Both`

Sends the selected frequency to both RX and TX.

`LED On`

Manually turns the TX light ON.

Use this to check static circuit behavior.

`LED Off`

Manually turns the TX light OFF.

Use this with a multimeter or comparator output LED to verify polarity.

`Raw 0x55`

Sends one Manchester byte:

```text
0x55 = 01010101
```

This is useful because it creates an alternating bit pattern. If RX cannot display this cleanly, full text packets will probably fail.

`Text`

The message to send.

`Send Text`

Sends a text packet:

```text
PREAMBLE 0x55 repeated
START    0x02
TYPE     0x01
LEN_MSB
LEN_LSB
PAYLOAD
CRC_MSB
CRC_LSB
STOP     0x03
```

## Debug Displays

`Live RX Bits`

Shows received bits as binary text, for example:

```text
01010101 01101000 01100101
```

`Decoded RX Bytes`

Shows received bytes as hex and binary:

```text
0x55 01010101
0x68 01101000
```

`Packet Status`

Shows the current result:

- `Success`
- `Failure`
- `Incomplete`
- `Unstable bit`
- `Sending`
- `Reset`

`Meaning`

Explains what the packet status means.

Examples:

- CRC matched
- CRC mismatch
- bad stop byte
- Manchester halves matched, so the bit is unstable

`RX Logic`

Shows RXCAP high/low/transitions.

`RX Counters`

Shows bit, byte, success, failure, and unstable-bit counters.

`Shared Log`

Combined RX and TX serial log.

`RX Log`

Receiver-only log.

`TX Log`

Transmitter-only log.

## Recommended First Test

1. Upload RX firmware to the RX board.
2. Upload TX firmware to the TX board.
3. Run the GUI.
4. Connect RX.
5. Connect TX.
6. Set `Freq` to:

```text
1000
```

7. Click `Set Both`.
8. Click `LED On` and `LED Off`.
9. Adjust `Invert TX` until LED behavior matches the circuit.
10. Use `RXCAP 1s` while toggling LED ON/OFF.
11. Adjust `Invert RX` until RX logic makes sense.
12. Click `Raw 0x55`.
13. Check if `Live RX Bits` shows an alternating pattern.
14. Send a short text like:

```text
hello
```

15. Only increase frequency after repeated `Success` results.

## Meaning Of Common Failures

`Unstable bit`

RX sampled both Manchester halves as the same value. This usually means:

- wrong threshold
- wrong polarity
- receiver too slow
- frequency too high
- LED not fully switching
- comparator output not clean

`Failure`

RX received a full packet, but CRC did not match. This means bits are arriving, but at least one byte is corrupted.

`Incomplete`

RX saw a packet start but did not receive the expected ending. This often means sync was lost mid-packet.

`No transitions in RXCAP`

RX is not seeing the optical signal as digital changes. Check wiring, polarity, comparator threshold, and TX LED switching.
