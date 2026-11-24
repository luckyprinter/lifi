# OpenVLC Academy

An interactive engineering course for the ESP32 visible-light communication prototype. Readers can follow the physical signal journey, model a file transfer, trace desktop settings across software and firmware, and inspect the actual implementation.

## Learning experience

- **Learning paths** build from the real prototype through hardware, protocol, software, and source-code reasoning. Completion is saved in the browser.
- **Signal Journey** traces eight stages across user actions, the desktop application, USB serial, firmware, and hardware.
- **Transfer Lab** models a file transfer in the browser, including frame inspection, optical symbols, dropped or corrupt frames, carousel repeats, CRC checks, and file reconstruction.
- **App Atlas** identifies which controls reach firmware and which plots use snapshots or synthetic data.
- **Code Studio**, **Deep Dive**, and **Practice** provide guided line explanations, an indexed full-repository reference, and code-reading exercises.

## Source provenance

The Academy pins the app and firmware to [OpenVLC-Public at 411f183](https://github.com/luckyprinter/OpenVLC-Public/tree/411f183a8592d8285118f613bb4909c5bbd9d3cc). The course follows the physical execution path. Alternate modules appear in the repository index so the inventory accurately reflects the snapshot. The protocol lab is an educational model with local file processing. Its waveforms and injected failures are synthetic. The thesis is the reference for experimental methodology and measurements.

## Development

Use Node.js 20 or newer.

```bash
npm ci
npm run dev
npm test
npm run build
npx playwright install --with-deps chromium
npm run test:visual
```

Run `npm run test:source -- ../OpenVLC-Public` with a checkout containing the pinned source commit. The visual suite saves screenshots to `artifacts/`. Set `ACADEMY_TEST_URL` to test an already-running preview, or `ACADEMY_CHROMIUM` to select a system Chromium for the test runner.

Pull requests build and run the checks in GitHub Actions. Pushes to `main` publish to [GitHub Pages](https://luckyprinter.github.io/lifi/). See [the development handoff](docs/ACADEMY-HANDOFF.md) for validation and limitations.
