# LiFi Thesis Project

This repository is now organized around the currently tested working LiFi
physical layer and the thesis paper workspace.

## Quick Start

Run the GUI from the repo root:

```bash
python Tx_gui.py
python Rx_gui.py
```

The root launchers call the stable GUI code without duplicating it.

## Main Folders

- `working_setup/` - preserved working firmware and GUI copies for the current
  physical setup.
- `paper/` - thesis draft material, references, definitions, instruments, and
  flowcharts.
- `web/` - React/Vite visual workflow and schematic app.
- `docs/` - project notes and baseline preservation notes.
- `firmware/` - stable and experimental Arduino/ESP32 sketches.
- `apps/` - stable and experimental Python GUI implementations.
- `debug_logs/` - saved TX/RX debug logs.
- `samples/` - received image/sample output.
- `tests/` - Python tests for protocol helpers.

## Current Working Physical Layer

TX:

```text
ESP32 GPIO 5 -> 2N3904 -> IRF540N -> 12 V DC LED bulb
```

RX:

```text
BPW34 photodiode -> OPA2604 TIA -> LM393 comparator -> ESP32 RX input
```

Core timing:

```cpp
halfBitUs = 1000000UL / (2 * frequencyHz);
```

This timing is the middle point of the system. TX must switch the LED at each
Manchester half-bit boundary, and RX must sample near the middle of each
Manchester half-bit.

## Thesis Workspace

Start here:

- `paper/chapter_1_introduction.md`
- `paper/chapter_2_related_literature_and_studies.md`
- `paper/chapter_3_methodology.md`
- `paper/flowcharts.md`
- `paper/research_instruments.md`
- `paper/definitions_of_terms.md`
- `paper/references.md`

## Web App

The React app is under:

```text
web/lifi-workflow-planner/
```

Run locally:

```bash
cd web/lifi-workflow-planner
npm install
npm run dev
```

The web app has been retargeted to this cleaned baseline. The schematic portion
is retained and updated for the current 2N3904 + IRF540N TX and BPW34 + OPA2604
+ LM393 RX setup.

## Development Rule

Before adding image, audio, video, FEC, carousel changes, or new driver
variants, verify text transfer on the working physical layer.

Recommended first test matrix:

```text
500 Hz
1000 Hz
2000 Hz
4000 Hz
9000 Hz
```

Record frequency, `halfBitUs`, comparator threshold, distance, payload, CRC
result, and any bit errors.
