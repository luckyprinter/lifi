# OpenVLC Academy

An animated, interactive technical field guide to the OpenVLC ESP32-based visible-light communication system.

## Source of truth

All technical content is based on **[luckyprinter/OpenVLC-Public](https://github.com/luckyprinter/OpenVLC-Public)**, pinned to commit `411f183a8592d8285118f613bb4909c5bbd9d3cc` (the latest commit inspected when this site was authored). The outdated contents formerly in this repository are not used as technical references.

The website is an explanatory companion, not a replacement for the source repository or the thesis. Where exact byte-level or implementation detail matters, follow the pinned source files and `firmware/specs/protocol_spec.md`.

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

## Included experiences

- TX-to-RX architecture map
- Animated end-to-end transmission walkthrough
- TX/RX application and firmware code excerpts linked to source
- Interactive protocol field explorer
- Hardware signal-chain guide
- CRC and BER validation explanations

## Deployment

The project is a Vite static site and can be deployed to Vercel. Set the project root to the repository root, build command to `npm run build`, and output directory to `dist`.

## Content accuracy

The current website is an initial working foundation. Some sections intentionally provide high-level explanations; they should be expanded against the pinned implementation before being treated as exhaustive function-by-function documentation. Never interpret illustrative snippets as a complete copy of the firmware.
