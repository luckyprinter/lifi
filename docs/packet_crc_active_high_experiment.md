# Packet CRC Active-High Experiment

Branch: `experiment/packet-crc-active-high-mosfet`

This experiment retests the older packet/CRC LiFi design instead of the current carousel/FEC design.

## Why

The remembered working system was closer to:

```text
start marker
data type: 1=text, 2=image, 3=audio
payload
end marker
CRC/error check
```

The closest repo match is the packet era around commit `1071b27`, especially:

- `firmware/experiments/packet_tx/packet_tx.ino`
- `firmware/experiments/packet_rx/packet_rx.ino`

## Firmware Added

- TX: `firmware/experiments/packet_crc_active_high_tx/packet_crc_active_high_tx.ino`
- RX: `firmware/experiments/packet_crc_active_high_rx/packet_crc_active_high_rx.ino`

Changes from the old packet firmware:

- ESP32 GPIO5 is used instead of Arduino pin 8.
- TX is active-high for the current MOSFET-only driver.
- Default frequency is `9000 Hz`.
- Packet type uses numeric values:
  - `1` = text
  - `2` = image placeholder
  - `3` = audio placeholder
- Packet format is:

```text
SOF 0x7E
type
sequence
length
payload
XOR CRC over type, sequence, length, and payload
```

An end packet is sent after a message:

```text
SOF 0x7E
type 0
sequence
length 0
CRC
```

## Serial Commands

TX:

```text
FREQ=9000
TYPE=1
SEND=hello
END
```

Any non-command line sent to TX is treated as text.

RX:

```text
FREQ=9000
DEBUG=1
INV=0
INV=1
STATS
RESETSTATS
RXCAP=100,10
```

Use `INV=1` if logs show alternating bytes like `0x55` but no valid packet start.

## Compile

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/experiments/packet_crc_active_high_tx
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/experiments/packet_crc_active_high_rx
```

## Upload

Current device convention:

```bash
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp32:esp32:esp32 firmware/experiments/packet_crc_active_high_rx
arduino-cli upload -p /dev/ttyUSB1 --fqbn esp32:esp32:esp32 firmware/experiments/packet_crc_active_high_tx
```

## First Test

Use the packet CRC GUI, not the stable carousel GUI:

```bash
./scripts/run_packet_crc_gui.sh
```

The GUI defaults to:

- RX: `/dev/ttyUSB0`
- TX: `/dev/ttyUSB1`

It writes logs to `debug_logs/packet_crc_gui_*.log`.

Live log files:

- Shared: `debug_logs/packet_crc_gui_shared_*.log`
- RX only: `debug_logs/packet_crc_gui_rx_*.log`
- TX only: `debug_logs/packet_crc_gui_tx_*.log`

The Save buttons create timestamped copies such as:

- `debug_logs/packet_crc_shared_copy_*.log`
- `debug_logs/packet_crc_rx_copy_*.log`
- `debug_logs/packet_crc_tx_copy_*.log`

## GUI Buttons

RX side:

- `Connect`: opens or closes the RX serial port, normally `/dev/ttyUSB0`.
- `Refresh`: rescans available serial ports.
- `Set RX Freq`: sends `FREQ=<value>` to RX.
- `Stats`: sends `STATS`; use this after a send attempt to see bytes, SOF count, OK packets, CRC failures, and unstable bits.
- `INV`: sends `INV=0` or `INV=1`. Try this when RX sees alternating bytes or no valid packets.
- `DEBUG`: sends `DEBUG=1` or `DEBUG=0`. Keep on for early tests.
- `RXCAP 100ms`: sends `RXCAP=100,10`, useful for `500 Hz` to `9000 Hz`.
- `RXCAP 2s`: sends `RXCAP=2000,100`, useful for slow tests like `1 Hz`.

TX side:

- `Connect`: opens or closes the TX serial port, normally `/dev/ttyUSB1`.
- `Set TX Freq`: sends `FREQ=<value>` to TX.
- `Set Type`: sends `TYPE=1`, `TYPE=2`, or `TYPE=3`.
- `Send`: sends `SEND=<message>`. For now, focus on text with `TYPE=1`.

Logs:

- `Shared Serial Log`: combined RX and TX activity in time order.
- `RX Terminal`: only RX output and RX commands.
- `TX Terminal`: only TX output and TX commands.
- `Copy ...`: copies that terminal text to clipboard.
- `Save ...`: saves a timestamped copy to `debug_logs`.
- `Clear`: clears only the shared visible log, not the live log files already written.

## Recommended Text Test Order

1. Upload the packet RX firmware to `/dev/ttyUSB0`.
2. Upload the packet TX firmware to `/dev/ttyUSB1`.
3. Run:

```bash
./scripts/run_packet_crc_gui.sh
```

4. Click RX `Connect`.
5. Click TX `Connect`.
6. Confirm frequency is `9000`.
7. Keep `TYPE=1`, message `1`, `INV` off, `DEBUG` on.
8. Click `Send`.
9. Look for:

```text
RX_PACKET_OK:type=1:seq=0:len=1
RX_TEXT_CHUNK:1
RX_MESSAGE_END:text=1
```

10. If it fails, click `Stats`, then try `INV` on and click `Send` again.
11. If it still fails, lower frequency in this order: `1000`, `500`, `100`, then send again at each step.

## Current Test Result

Latest packet GUI logs:

- Shared: `debug_logs/packet_crc_gui_shared_20260519_152255.log`
- RX: `debug_logs/packet_crc_gui_rx_20260519_152255.log`
- TX: `debug_logs/packet_crc_gui_tx_20260519_152255.log`

Observed:

- TX sent packets repeatedly, for example `SEND=sad`, with `TX_PACKET_SENT:type=1:seq=0:len=3:crc=0x74`.
- RX did not report `RX_PACKET_OK`.
- RX stats at `1000 Hz`: `sof=0`, `ok=0`, `crcFail=0`, with unstable Manchester bits.
- `INV=1` was tried and still did not produce packet sync.
- At `9000 Hz`, RX capture showed `high=0`, `transitions=0`.
- At `200 Hz`, `RXCAP=2000,100` showed real input activity: `high=1218`, `low=18571`, `transitions=882`.
- At `200 Hz` down to `10 Hz`, RX repeatedly decoded a similar wrong byte pattern such as `0x03 0xFB 0xFF 0xC8 0x93 0xA6 0xC5...`.

Interpretation:

- The packet firmware is transmitting, and the RX input is not completely dead at lower frequencies.
- The RX decoder is not aligning to `SOF=0x7E`; this is probably sync edge, Manchester phase, or bit polarity/timing rather than packet CRC itself.
- Next best firmware step is to add RX edge/phase options so the same optical waveform can be decoded with alternate sync timing before changing the hardware again.

Manual serial test:

1. Open RX serial monitor or packet CRC GUI log on `/dev/ttyUSB0`.
2. Send RX:

```text
FREQ=9000
INV=0
DEBUG=1
```

3. Open TX serial monitor on `/dev/ttyUSB1`.
4. Send TX:

```text
FREQ=9000
SEND=1
```

Expected RX success lines:

```text
RX_PACKET_OK:type=1:seq=0:len=1
RX_TEXT_CHUNK:1
RX_PACKET_OK:type=0:seq=1:len=0
RX_MESSAGE_END:text=1
```

If that fails, try `INV=1` on RX and repeat.

## Current RX Hardware Update: TEPT4400 + LM393

Current receiver front-end:

- Sensor: `TEPT4400`
- Comparator: `LM393`
- `+IN`: TEPT4400 signal
- `-IN`: threshold from `10k ohm` potentiometer across `3.3 V`
- Comparator output: should go to ESP32 RX input, preferably GPIO5 for the digital packet/carousel firmware
- Measured TEPT4400 behavior:
  - light present: near `0 V`
  - no light / dark: about `2.3 V`

Important LM393 notes:

- LM393 outputs are usually open-collector/open-drain style. The output needs a pull-up.
- Pull the LM393 output up to `3.3 V`, not `5 V`, when feeding an ESP32 GPIO.
- All grounds must be common: RX ESP32 ground, LM393 ground, TEPT4400 ground, and TX supply ground if measurements share reference.

Expected polarity with this wiring:

- Current TEPT4400 measurement: strong light makes the sensor node near `0 V`, and no light lets it rise to about `2.3 V`.
- Because TEPT4400 is on `+IN` and the pot threshold is on `-IN`, the LM393 output should indicate:
  - light ON / TEPT low / `+IN < -IN` -> output LOW
  - light OFF / TEPT high / `+IN > -IN` -> output HIGH
- For the current active-high packet TX, this means the physical LM393 output is likely `dark = HIGH`, `light = LOW`.
- The packet RX firmware should therefore be tested with `INV=1` first, because `INV=0` treats the dark-high comparator output as the direct Manchester logic and can invert the decoded bits.

Latest `20260519_231343` packet log:

- TX sent `SEND=1` packets at `9000 Hz`.
- RX was set to `INV=0`.
- RX produced many `RX_ERROR:unstable_manchester_bit` lines and no `RX_PACKET_OK`.

Next LM393 test:

1. Set TX/RX frequency to `1000 Hz` first.
2. Set RX `INV=1`.
3. Adjust the potentiometer so the LM393 output LED/output changes state cleanly between TX LED on and off at slow speed.
4. Run:

```text
RXCAP=2000,50
STATS
```

5. Send:

```text
SEND=1
```

6. If `1000 Hz` works, raise to `3000`, `5000`, then `9000 Hz`.

## Shared ChatGPT Conversation Finding

Shared conversation checked:

- `https://chatgpt.com/share/69fddf92-1a34-83ec-9f7d-1dd195c277cd`
- Local saved copy: `debug_logs/shared_chatgpt_69fddf92.html`

The shared conversation points more strongly to the carousel/file-transfer era than the packet CRC era. It describes a setup where the link was close to working and the problem was one missing final image chunk, not total RX sync failure.

Important clues from that conversation:

- TX circuit used a `2N3904` inverter stage with an `IRF540N` gate pull-up.
- The TX firmware was active-low idle-ON:
  - ESP32 GPIO `LOW` = LED ON.
  - ESP32 GPIO `HIGH` = LED OFF.
  - After each frame and frame gap, the bulb returned to ON.
- The recommended test was `9000 Hz`, `512` byte chunks, and `3` carousel rounds.
- The GUI fix padded the last short chunk to the full chunk size during optical transmission, while RX saved only the real byte count.
- The old failure described there was `chunk 20/20` missing where the final chunk was only about `100` bytes. That is different from the current failure, where RX does not even detect valid preamble/packet sync.

Local repo files matching the shared conversation:

- Active-low idle-ON TX firmware: `.history/firmware/stable/tx/tx_20260509042645.ino`
- Padded final-chunk TX GUI: `.history/apps/stable/Tx_gui_20260509042013.py`
- Matching carousel RX GUI: `.history/apps/stable/Rx_gui_20260509042004.py`
- Matching carousel RX firmware: `.history/firmware/stable/rx/rx_20260509041644.ino`

Key code behavior in the old active-low TX:

```cpp
inline void txLightOn() {
  gpio_set_level((gpio_num_t)TX_PIN, 0);
}

inline void txLightOff() {
  gpio_set_level((gpio_num_t)TX_PIN, 1);
}
```

Key code behavior in the old padded TX GUI:

```python
if real_len < chunk_size:
    padded_chunk = chunk + bytes(chunk_size - real_len)
else:
    padded_chunk = chunk
```

Current conclusion:

- The packet CRC experiment is still useful for a small text-only sync test.
- But the shared ChatGPT evidence says the remembered `9 kHz` working setup was most likely active-low carousel with padded chunks and the `2N3904` inverter driver, not the current MOSFET-only active-high setup.
- Since the user is currently not using the `2N3904`, software can mimic idle-ON and padded carousel framing, but it cannot fully reproduce the old gate-drive edge speed and optical waveform.
