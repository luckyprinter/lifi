# LiFi Project Context For Future Codex Sessions

This file is the durable repo footprint for the LiFi workflow planner. Read it before making future changes, especially if the original device that hosted the planner server is turned off.

## Current Direction

The project is a low-cost visible light communication thesis system. The main path is:

1. PC TX GUI prepares text/file/media data.
2. TX ESP32 receives frames over USB serial.
3. TX ESP32 Manchester-encodes frames through an LED driver.
4. Visible light carries data to the receiver.
5. TEPT4400 or future photodiode/phototransistor front-end converts light into voltage.
6. RX ESP32 thresholds and Manchester-decodes the signal.
7. RX GUI rebuilds chunks, applies simple XOR FEC, checks CRC, and saves/display output.

## Current Debug Priority

The main known bottleneck is RX synchronization/recovery. Debug logs show:

- TX sends frames and reports done markers.
- RX sees transitions/decoded bytes.
- `framesOk` stays at zero in debug sessions.
- `unstableBits` rises.
- Some frames fail CRC or header parsing.

The most suspicious code-level regression compared with commit `4d78a01518c4d2498311b291501e6e98577580e3`:

- Known-good RX used GPIO5 digital input, `9000 Hz`, absolute `micros()` deadlines, and `majorityRead()`.
- Current RX defaults to GPIO34 ADC thresholding, `1000 Hz`, a different sync edge, and single-sample `readRxPin()` in the active Manchester decoder.

## Recommended Recovery Path

Start from known-good behavior and add modern features one at a time:

1. Reproduce old settings: `9000 Hz`, chunk `512`, rounds `2`, FEC on.
2. Restore `majorityRead()` inside current `receiveManchesterByte()`.
3. Add runtime sync edge control again: `EDGE=LH/HL`.
4. Compare old GPIO5 digital input versus current GPIO34 ADC thresholding.
5. Verify TX polarity with `LEDTEST` before changing `LED_ACTIVE_LOW`.
6. Sweep test frequencies from `1-15 kHz`.

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

