# LiFi Project Context For Future Codex Sessions

This file is the durable repo footprint for the LiFi workflow planner. Read it before making future changes, especially if the original device that hosted the planner server is turned off.

## Current Direction

The project is a low-cost visible light communication thesis system. The main path is:

1. PC TX GUI prepares text/file/media data.
2. TX ESP32 receives frames over USB serial.
3. TX ESP32 Manchester-encodes frames through an LED driver.
4. Visible light carries data to the receiver.
5. TEPT4400 front-end converts light into voltage.
6. LM393 comparator thresholds the TEPT4400 voltage into a digital signal for the RX ESP32.
7. RX ESP32 Manchester-decodes the signal.
8. RX GUI rebuilds chunks, applies simple XOR FEC, checks CRC, and saves/display output.

## Current Debug Priority

The main known bottleneck is RX signal recovery before protocol decoding. Debug logs show:

- TX sends frames and reports done markers.
- RX firmware may decode bytes, but they are not valid Manchester/protocol bytes.
- `framesOk` stays at zero in debug sessions.
- `unstableBits` rises.
- In the latest `4d78a` baseline retest, RX never sees a valid preamble.

Latest baseline retest state:

- Branch: `experiment/4d78a-rx-current-tx-driver`.
- Firmware/GUI restored from `4d78a01`, with TX changed to active-high for the current non-2N3904 driver.
- RX uploaded to `/dev/ttyUSB0`; TX uploaded to `/dev/ttyUSB1`.
- User measured RX phototransistor node:
  - idle light ON: about `0.01 V`
  - during transmission: about `0.4 V` to `1.5 V`
  - no received light can let the node rise to about `3.3 V`
  - at low-frequency TX tests, `1 Hz` and `30 Hz`, the TX fully turns ON/OFF and RX swings about `0.1 V` to `3 V`
- User reports an earlier matched RX/TX setup successfully transmitted text at about `9 kHz`, so do not assume 9 kHz is impossible for this project.
- User reports the main hardware difference now is the TX driver: new MOSFET-only path without the previous `2N3904` stage.
- Current RX front-end update: TEPT4400 signal is wired to LM393 `+IN`; a `10k ohm` potentiometer across `3.3 V` sets the LM393 `-IN` threshold.
- Current TEPT4400 measurement: light present drives the sensor node near `0 V`; no light drives it to about `2.3 V`.
- Monitor log: `debug_logs/rx_gui_monitor_20260519_133207.log`
- Key RX test line: `RX_DIGITAL_TEST:durationMs=1000:samples=19238:high=0:low=19238:transitions=0:final=0`
- Key RX stats line: `RX_STATS:freq=1000:halfBitUs=500:pin=5:raw=0:bytes=3100:unstableBits=4188:badCrc=0:framesOk=0:preambleBytes=0:maxPreambleRun=0`

Interpretation:

- GPIO5 digital RX is not receiving valid HIGH logic from the current phototransistor voltage swing.
- The link is failing before CRC/FEC; RX never detects `0xAA` preamble bytes.
- Mostly decoded `0xFF` means the old digital decoder is locking onto invalid/biased levels rather than real frames.
- Low-frequency tests prove the TX can fully turn ON/OFF and the RX node can cross ESP32 logic levels. The likely bottleneck is now frequency response, RC settling, sampling phase, or high-rate optical contrast collapse.
- The historical 9 kHz working point means the current failure is probably due to differences from that matched era: TX driver/light source behavior, active-high/active-low polarity, idle state, RX sampling phase, or digital-vs-ADC threshold interpretation.
- Because the only reported hardware difference is removal of the `2N3904` stage, prioritize TX driver waveform checks at `9 kHz`: ESP32 GPIO, MOSFET gate, drain/LED node, and RX sensor node.
- Latest RX log `debug_logs/rx_gui_monitor_20260519_143747.log`: top decoded bytes were mostly `0xFF` and `0x55`; `framesOk=0`, `preambleBytes=0`, `maxPreambleRun=0`; digital captures at `1000 Hz`, `500 Hz`, and `1 Hz` saw `high=0`, `transitions=0`.
- A `100 ms` capture at `1 Hz` can miss transitions because half-bit time is `500 ms`; use `RXCAP=2000,100` for very slow tests.
- Repeated `0x55` during slow tests suggests alternating waveform/polarity or phase mismatch, not successful protocol sync.
- A `1 V` decision level cannot be set on GPIO5 digital mode. Use GPIO34 ADC thresholding or an external comparator/Schmitt stage for that.
- If the phototransistor front-end is supplied from `5 V`, never feed that node directly into ESP32 GPIO/ADC. Limit the ESP32 input to `0-3.3 V` with a divider/clamp, or use a comparator output pulled up to `3.3 V`.
- LM393 output should be pulled up to `3.3 V` before ESP32 GPIO. With TEPT4400 on `+IN`, threshold on `-IN`, and measured light = near `0 V`, no-light = about `2.3 V`, likely polarity is light ON = LOW and light OFF/dark = HIGH.
- For the current active-high packet TX, test the packet RX with `INV=1` first. Latest packet logs from `20260519_231343` used `INV=0` at `9000 Hz` and showed many unstable Manchester bits with no `RX_PACKET_OK`.

## Remembered Older Protocol

The user clarified that the older working design may not have been carousel. The remembered structure was:

1. start bit / start marker
2. data type, where `1=text`, `2=image`, `3=audio`
3. payload data
4. stop bit / end transmission
5. CRC/error check in the CRC-era variant

Closest repo match:

- `firmware/experiments/packet_tx/packet_tx.ino`
- `firmware/experiments/packet_rx/packet_rx.ino`
- Introduced around commit `1071b27` and present after `72a7d84`
- Actual packet format there: `SOF=0x7E`, type byte, sequence byte, length byte, payload, XOR CRC
- New experiment branch created: `experiment/packet-crc-active-high-mosfet`.
- New controlled firmware:
  - TX: `firmware/experiments/packet_crc_active_high_tx/packet_crc_active_high_tx.ino`
  - RX: `firmware/experiments/packet_crc_active_high_rx/packet_crc_active_high_rx.ino`
- GUI for this experiment: `apps/experiments/packet_crc_gui.py`.
- Run script: `./scripts/run_packet_crc_gui.sh`.
- Do not use the stable carousel GUI for this packet test; it sends carousel/FEC frames, not the packet CRC `SEND=` command protocol.
- Packet GUI has live shared/RX/TX terminals and auto-writes:
  - `debug_logs/packet_crc_gui_shared_*.log`
  - `debug_logs/packet_crc_gui_rx_*.log`
  - `debug_logs/packet_crc_gui_tx_*.log`
- Packet GUI Save buttons create timestamped copies:
  - `debug_logs/packet_crc_shared_copy_*.log`
  - `debug_logs/packet_crc_rx_copy_*.log`
  - `debug_logs/packet_crc_tx_copy_*.log`
- Both new packet CRC sketches compile for `esp32:esp32:esp32`.

The most suspicious code-level regression compared with commit `4d78a01518c4d2498311b291501e6e98577580e3`:

- Known-good RX used GPIO5 digital input, `9000 Hz`, absolute `micros()` deadlines, and `majorityRead()`.
- Current RX defaults to GPIO34 ADC thresholding, `1000 Hz`, a different sync edge, and single-sample `readRxPin()` in the active Manchester decoder.

## Shared ChatGPT Conversation Evidence

The user provided an old shared conversation:

- `https://chatgpt.com/share/69fddf92-1a34-83ec-9f7d-1dd195c277cd`
- Local fetched copy: `debug_logs/shared_chatgpt_69fddf92.html`

This evidence points back toward the carousel/file-transfer era. In that conversation, the system was close enough to receive most image chunks; the highlighted failure was a missing final short chunk, not a total sync failure.

Most important clues:

- TX used the older `2N3904` inverter plus `IRF540N` gate-drive idea.
- TX firmware was active-low idle-ON:
  - GPIO `LOW` = LED ON.
  - GPIO `HIGH` = LED OFF.
  - idle and gaps return to LED ON.
- The suggested old working test was `9000 Hz`, `512` byte chunk size, `3` carousel rounds.
- The GUI fix padded final short chunks optically while preserving `real_len` so RX saved only the real bytes.

Matching local repo history:

- `.history/firmware/stable/tx/tx_20260509042645.ino`
- `.history/apps/stable/Tx_gui_20260509042013.py`
- `.history/apps/stable/Rx_gui_20260509042004.py`
- `.history/firmware/stable/rx/rx_20260509041644.ino`

Updated interpretation:

- Packet CRC remains useful for a very small text-first decoder isolation test.
- But the best match for the remembered `9 kHz` success is active-low carousel with padded chunks and the old `2N3904` inverter driver.
- The current no-2N3904 TX can be software-adjusted for polarity/idle behavior, but it may not reproduce the old 12 V gate-drive edge speed or optical waveform.

## Recommended Recovery Path

Start from known-good behavior and add modern features one at a time:

1. Prefer hardware cleanup next: comparator/Schmitt trigger or TIA/comparator front-end to produce 0/3.3 V logic for GPIO5.
2. If staying software-only, return to GPIO34 ADC threshold mode and combine midpoint threshold, majority sampling, and edge/phase controls.
3. Test RX node and logic output at `1, 3, 5, 9, 12, 15 kHz`.
4. Keep TX active-high for the current driver unless a direct LEDTEST proves otherwise.
5. Avoid interpreting CRC/FEC failures until RX reports valid preamble/frame starts.
6. Next recommended test: sweep `30, 100, 300, 500, 1000, 3000, 5000, 9000, 12000, 15000 Hz` using `RXTEST=1000` and compare high/low/transition counts.
7. Specifically compare `9 kHz` current TX waveform/logic behavior against the remembered working setup before making permanent RX hardware changes.
8. If a scope or logic analyzer is available, inspect the MOSFET gate/drain at `9 kHz`; if not, use RX voltage and `RXTEST` sweep as the proxy.
9. RX firmware now has direct capture helpers:
   - `RXCAP=100,10` for GPIO5 digital capture.
   - `ADCAP=100,100,1000` for GPIO34 millivolt capture with a `1000 mV` threshold. GPIO34 must be safely wired and kept within `0-3.3 V`.
10. Create a controlled branch from the packet CRC era if the goal is to retest the remembered start/type/data/stop design.
11. Create a controlled carousel compatibility branch from the `.history` files above if the goal is to reproduce the old shared-conversation `9 kHz` behavior. Change only the TX polarity/driver assumption needed for the current MOSFET-only hardware.

## Planner State

The web planner stores browser-local state in `localStorage`. If run with:

```bash
cd web/lifi-workflow-planner
npm run app
```

then `Submit status` can write the latest planner notes and schematic edits into:

- `web/lifi-workflow-planner/handoffs/latest.json`
- `web/lifi-workflow-planner/handoffs/latest.md`

If this machine/server is off, those live files may not exist or may be stale. Use this `PROJECT_CONTEXT.md`, `docs/lifi_system_workflow.md`, and committed code/logs as the durable baseline.

## Cross-Device Reality

Automatic cross-device sync requires an always-available remote or a commit/push/pull workflow. A local server cannot sync when the host device is powered off.

Possible future sync options:

- Commit `handoffs/latest.md` and `latest.json` to GitHub after meaningful planner updates.
- Add a GitHub-backed save action later.
- Use a cloud sync folder outside the repo if desired.
