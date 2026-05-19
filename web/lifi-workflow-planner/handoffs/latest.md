# LiFi Handoff - 2026-05-19 13:45 Asia/Manila

## Current Branch

`experiment/4d78a-rx-current-tx-driver`

## Current Test State

The project is retesting the `4d78a01` known-good baseline with the RX/GUI restored from that era and TX patched active-high for the current non-2N3904 driver.

Uploaded firmware:

- RX: `/dev/ttyUSB0`
- TX: `/dev/ttyUSB1`

User measurement:

- RX phototransistor node idle light ON: about `0.01 V`
- RX phototransistor node during transmission: about `0.4 V` to `1.5 V`
- RX phototransistor node with no received light: can rise to about `3.3 V`
- Current TEPT4400 + LM393 setup measurement: TEPT4400 node is near `0 V` with light and about `2.3 V` with no light.
- Low-frequency TX tests at `1 Hz` and `30 Hz`: TX fully turns ON/OFF, RX swings about `0.1 V` to `3 V`
- Historical working point: previous matched RX/TX setup transmitted text at about `9 kHz`
- Current hardware difference: TX uses the new MOSFET-only driver without the previous `2N3904` stage
- Current RX hardware update: TEPT4400 feeds an LM393 comparator. TEPT4400 signal is on `+IN`; a `10k ohm` potentiometer across `3.3 V` sets the threshold on `-IN`.

Key RX monitor log:

- `debug_logs/rx_gui_monitor_20260519_133207.log`
- `RX_DIGITAL_TEST:durationMs=1000:samples=19238:high=0:low=19238:transitions=0:final=0`
- `RX_STATS:freq=1000:halfBitUs=500:pin=5:raw=0:bytes=3100:unstableBits=4188:badCrc=0:framesOk=0:preambleBytes=0:maxPreambleRun=0`

Interpretation:

- The GPIO5 digital RX baseline is not receiving valid ESP32 HIGH logic.
- The receiver decodes mostly garbage bytes, especially `0xFF`, and never detects a valid `0xAA` preamble run.
- Failure is before CRC/FEC. Do not focus on file reconstruction yet.
- The newest low-frequency test reduces suspicion that TX polarity is simply wrong. The next likely bottleneck is frequency response: the RX waveform is good at `1-30 Hz`, but collapses near communication rates.
- Since an older setup worked at `9 kHz`, avoid concluding that the project cannot run at 9 kHz. Focus on what changed: TX driver/light source, polarity/idle behavior, RX sampling, or threshold mode.
- Since the only reported hardware change is MOSFET-only TX without `2N3904`, prioritize checking whether the TX gate/drain/LED current waveform still has enough optical depth and edge speed at `9 kHz`.
- Latest RX log: mostly `0xFF`, many `0x55`, no `RX_FRAME_START`, no valid carousel frames. Digital captures at `1000 Hz`, `500 Hz`, and `1 Hz` reported `high=0`, `transitions=0`.
- The `1 Hz` capture used `100 ms`, which is shorter than one `500 ms` half-bit; for slow tests use `RXCAP=2000,100`.
- Repeated `0x55` during slow tests points toward polarity/phase mismatch or an alternating waveform that is not being interpreted as the expected carousel preamble.
- GPIO5 digital HIGH/LOW threshold is decided by the ESP32 input buffer. A `1 V` threshold needs ADC mode or a comparator/Schmitt trigger.
- Do not feed a `5 V` phototransistor node directly to ESP32 GPIO/ADC. Use a divider/clamp or comparator output pulled up to `3.3 V`.
- LM393 output should be pulled up to `3.3 V` when feeding ESP32 GPIO. With TEPT4400 on `+IN`, threshold on `-IN`, and measured TEPT4400 behavior of light = near `0 V`, no light = about `2.3 V`, expected comparator polarity is light ON = LM393 output LOW and light OFF/dark = LM393 output HIGH. For the current active-high packet TX, try packet RX `INV=1` first.

## Older Protocol Clue

User clarified the remembered working design may have been CRC packet framing, not carousel:

- start bit / marker
- data type: `1=text`, `2=image`, `3=audio`
- payload data
- stop bit / end transmission
- CRC/error check

Closest repo match found: `firmware/experiments/packet_tx/packet_tx.ino` and `firmware/experiments/packet_rx/packet_rx.ino`, introduced around `1071b27`. That pair uses `SOF=0x7E`, type, sequence, length, payload, and XOR CRC.

New branch created for this direction:

- Branch: `experiment/packet-crc-active-high-mosfet`
- TX: `firmware/experiments/packet_crc_active_high_tx/packet_crc_active_high_tx.ino`
- RX: `firmware/experiments/packet_crc_active_high_rx/packet_crc_active_high_rx.ino`
- GUI: `apps/experiments/packet_crc_gui.py`
- Launcher: `./scripts/run_packet_crc_gui.sh`
- Experiment guide: `docs/packet_crc_active_high_experiment.md`
- Compile status: both packet CRC sketches compile for `esp32:esp32:esp32`.
- Important: use the packet CRC GUI for this branch, not the stable carousel GUI.
- Packet GUI has separate shared/RX/TX terminals and timestamped Save buttons. Read logs from `debug_logs/packet_crc_gui_shared_*.log`, `packet_crc_gui_rx_*.log`, and `packet_crc_gui_tx_*.log`.
- Latest packet test logs from `20260519_152255`: TX sent packet CRC frames, RX saw no `RX_PACKET_OK`; `INV=1` was tried; `9000 Hz` capture had `high=0/transitions=0`, while `200 Hz` capture had `high=1218`, `low=18571`, `transitions=882`. RX repeatedly decoded a stable wrong byte pattern such as `0x03 0xFB 0xFF 0xC8...`, pointing to sync edge/phase/polarity timing rather than CRC.
- Latest packet test logs from `20260519_231343`: TX sent `SEND=1` at `9000 Hz`; RX was set to `INV=0`; RX produced many `RX_ERROR:unstable_manchester_bit` lines and no `RX_PACKET_OK`. Since the new LM393 wiring likely makes dark = HIGH and light = LOW, the next packet test should use `INV=1`, starting at `1000 Hz`.

## Shared ChatGPT Conversation Finding

User provided a shared old ChatGPT conversation:

- `https://chatgpt.com/share/69fddf92-1a34-83ec-9f7d-1dd195c277cd`
- Saved local copy: `debug_logs/shared_chatgpt_69fddf92.html`

Main finding: the shared conversation points more strongly to the old carousel/file-transfer setup than the packet CRC setup. The link was not totally dead then; it was close enough to receive image chunks, and the noted issue was the last short chunk not completing.

Relevant old setup:

- TX hardware used a `2N3904` inverter stage with `IRF540N`, not the current MOSFET-only driver.
- TX firmware was active-low idle-ON:
  - ESP32 GPIO `LOW` = LED ON.
  - ESP32 GPIO `HIGH` = LED OFF.
  - Frame gaps and idle returned the bulb to ON.
- Old recommended test: `9000 Hz`, `512` byte chunks, `3` carousel rounds.
- Old GUI fix: pad the final short chunk to `chunk_size` for optical transmission, but preserve `real_len` so RX saves only the real bytes.

Local repo files that match that shared conversation:

- `.history/firmware/stable/tx/tx_20260509042645.ino`
- `.history/apps/stable/Tx_gui_20260509042013.py`
- `.history/apps/stable/Rx_gui_20260509042004.py`
- `.history/firmware/stable/rx/rx_20260509041644.ino`

Interpretation update:

- The remembered `9 kHz` working setup was probably active-low carousel with padded chunks and the `2N3904` inverter driver.
- The current packet CRC branch remains useful as a text-first decoder isolation test, but it may not reproduce the old working setup.
- The current no-2N3904 TX can switch visibly at low frequency, but it may not reproduce the old 12 V gate-drive edge speed and optical contrast at `9 kHz`.
- If the goal is to reproduce the old success, create or use a carousel compatibility branch based on those `.history` files, then adapt only TX polarity/driver assumptions for the current MOSFET.

## Recommended Next Decision

Pick one:

1. Hardware cleanup: add comparator/Schmitt trigger/TIA so GPIO5 sees clean `0 V / 3.3 V` logic.
2. Software recovery: return to GPIO34 ADC threshold mode, but add midpoint thresholding, majority sampling, and edge/phase controls.
3. Quick hardware experiment: adjust phototransistor load/pull-up path and retest `RX_DIGITAL_TEST` at `1, 3, 5, 9, 12, 15 kHz`.
4. Frequency sweep: use `RXTEST=1000` at `30, 100, 300, 500, 1000, 3000, 5000, 9000, 12000, 15000 Hz` to find where transitions disappear.
5. Compare the current `9 kHz` waveform against the remembered working `9 kHz` behavior before permanently changing the RX front-end.
6. If possible, measure ESP32 TX GPIO, MOSFET gate, MOSFET drain/LED node, and RX phototransistor node at `9 kHz`.
7. New firmware/GUI capture tools:
   - `RXCAP=100,10` reads GPIO5 digital level quickly.
   - `ADCAP=100,100,1000` reads GPIO34 millivolts with a `1000 mV` decision threshold. Wire GPIO34 only if the node is limited to `0-3.3 V`.
8. For `1 Hz` tests, use `RXCAP=2000,100` so the capture spans multiple half-bits.
9. Retest the packet CRC era if the goal is to reproduce the remembered start/type/data/stop design.
10. Retest the shared-conversation carousel era if the goal is to reproduce the remembered `9 kHz` working setup: start from the `.history` active-low idle-ON TX plus padded GUI, then change only the minimum needed for the current no-2N3904 TX driver.
11. For the TEPT4400 + LM393 RX, tune the potentiometer at slow frequency first, confirm `RXCAP=2000,50` shows clean high/low transitions, then send `SEND=1` with `INV=1` at `1000`, `3000`, `5000`, and `9000 Hz`.

## GUI Changes In Progress

- RX GUI has `RX Test`, `Stats`, `Reset Stats`, `Save Log`, `Clear Log`.
- RX GUI auto-saves monitor logs to `debug_logs/rx_gui_monitor_*.log`.
- RX/TX GUIs now default to `/dev/ttyUSB0` and `/dev/ttyUSB1` respectively.
- RX/TX GUIs are being made smaller-screen friendly and copy-friendly.
