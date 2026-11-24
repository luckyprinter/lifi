# OpenVLC Academy

An interactive, mobile-first engineering course for understanding the physical ESP32 visible-light communication prototype, from the optical hardware and protocol to the firmware and desktop application code.

## Source provenance

- **Firmware and protocol baseline:** `luckyprinter/OpenVLC-Public` commit `411f183a8592d8285118f613bb4909c5bbd9d3cc` (the current `main` branch head as checked on 2026-11-24).
- **Desktop application snapshot:** `luckyprinter/OpenVLC-Public` draft PR #18 head `80ef4afa63a3fe571ffd5026560bf7d7d90fbecc`. This is unfinished development work and is explicitly labelled as such.
- The application snapshot is not represented as part of the thesis-tested firmware baseline. PR #18 is still a draft and its hardware-dependent behavior has not been physically validated by this site.
- The physical architecture is the teaching focus. Conceptual animations explain the signal path; they are not live hardware telemetry or measured oscilloscope captures.

## Learning experiences

- Six progressive learning paths from project orientation to coding practice.
- An eight-stage animated physical signal journey.
- Responsive, stage-specific visual models rather than one cropped desktop diagram.
- Source code studio with pinned commit links, exact line ranges, syntax highlighting, and selectable line-by-line explanations.
- Initial guided examples for TX application state, USB serial handshake, 4B5B encoding, GPIO symbol output, frame construction, RX majority sampling, byte decoding, and frame validation.
- A short knowledge-check interaction.
- Playwright responsive smoke tests covering the home, signal journey, code studio, and focused lessons at 320, 360, 390, 430, 768, 1024, and 1366 CSS-pixel widths; CI stores screenshots as workflow artifacts.

## Accuracy and teaching policy

The website distinguishes the physical prototype from explanatory models. It does not present a simulation backend as the experimental system, invent live optical telemetry, or imply that CI proves ESP32/USB/optical performance. Source excerpts must match the pinned repository commit and displayed line numbers. The thesis remains authoritative for experimental methodology and measured results.

## Local development

Requirements: Node.js 20+ and npm.

```bash
npm install
npm run dev
npm run build
```

The visual test command expects Chromium installed through `npx playwright install --with-deps chromium`.

## Deployment

The static Vite application is deployed through GitHub Pages. Vercel deployment remains deferred and is not configured by this work.
