# OpenVLC Field Guide

An animated, interactive technical guide to the ESP32 visible-light communication prototype, with source excerpts linked to exact GitHub lines.

## Source snapshots and provenance

The site deliberately separates two source snapshots:

- **Firmware / protocol baseline:** `luckyprinter/OpenVLC-Public` commit `411f183a8592d8285118f613bb4909c5bbd9d3cc`. The firmware files were not changed by the desktop-app redesign branch, so firmware excerpts link to this fixed thesis-artifact baseline.
- **Desktop application development snapshot:** branch `redesign/product-shell-method2`, commit `80ef4afa63a3fe571ffd5026560bf7d7d90fbecc`, from draft [PR #18](https://github.com/luckyprinter/OpenVLC-Public/pull/18). This is unfinished development work and is not merged into `main`. App excerpts are pinned to this exact commit.

The application code still contains optional simulation backends, but TX and RX application state default to physical mode. The software-architecture switch on this website changes only the explanatory diagram; it does not connect to hardware or execute the Python application.

The PR #18 development notes include important capability limits: the current firmware/host protocol does not stream raw symbol-rate comparator samples, so the live receiver trend is based on PVo/Vref/margin telemetry rather than a fabricated OOK waveform. No physical ESP32 or optical-link validation is implied by desktop CI.

The thesis remains the authority for experimental methodology and measured results. The website is an explanatory companion, not a replacement for the source repository or thesis.

## Included experiences

- Chapter-based learning navigation
- Animated end-to-end transmission walkthrough
- Step-by-step source code excerpts with exact file, line range, and pinned GitHub links
- Interactive 4B5B encoder/decoder and NRZ/OOK waveform
- Receiver sampling, synchronization, decoding, and CRC walkthrough
- Hardware signal-chain guide and Vref calibration explanation
- CRC versus reference-file BER explanation
- Desktop-app development notes covering serial discovery, telemetry honesty, Method 2 BER, and bounded batch reconstruction

## Local development

Requirements: Node.js 20+ and npm.

```bash
npm install
npm run dev
```

Production build:

```bash
npm run build
npm run preview
```

## Deployment

The project is a Vite static site deployed through GitHub Pages. Vercel deployment remains separate and is not configured by this change.
