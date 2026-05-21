# LiFi Thesis Paper Workspace

This folder contains thesis-writing notes and draft material for the current
working LiFi communication system.

## Files

- `chapter_1_introduction.md` - sample Chapter 1 draft.
- `chapter_2_related_literature_and_studies.md` - related literature and studies with source links.
- `chapter_3_methodology.md` - sample methodology based on the current implementation.
- `definitions_of_terms.md` - project-specific definitions.
- `research_instruments.md` - hardware, software, and measurement instruments.
- `flowcharts.md` - TX, RX, and full-system flowcharts.
- `references.md` - source map for thesis citation cleanup.

## Current Thesis Baseline

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

Treat text transmission as the first controlled experiment before image, audio,
and video expansion.
