# LiFi Workflow Planner

Interactive React diagram app for explaining the LiFi thesis system flow.

## Run

From the repo root:

```bash
./scripts/run_lifi_workflow_planner.sh
```

Open:

```text
http://localhost:5174/
```

For Vite development from this folder:

```bash
npm install
npm run dev -- --port 5173
```

Open:

```text
http://localhost:5173/
```

## Build

```bash
npm run build
```

The built app is written to `dist/`. It is now a PWA, so after it is opened once from a real local/hosted URL, the browser can cache it for offline use.

## Offline And Sharing

Recommended sharing path:

1. Build the app:

```bash
npm run build
```

2. Upload the `dist/` folder to a static host such as GitHub Pages, Netlify, or Vercel.
3. Share the hosted link.
4. On Android, open the link in Chrome and choose `Add to Home screen` or `Install app`.

For local presentation without internet:

```bash
npm run app
```

Open:

```text
http://localhost:5174/
```

To let another phone/laptop on the same Wi-Fi view it, open the same app using this computer's LAN IP:

```text
http://YOUR_LAPTOP_IP:5174/
```

If you only share the raw `dist/` folder, use a tiny static server to view it. Browser service workers do not work reliably from a direct `file://` open.

Offline limitations:

- Diagrams, schematic values, and notes can work locally in the browser after first load.
- `Submit status` only writes to repo files when using `npm run app` on the host computer.
- Cross-device sync still needs a running host, GitHub, or another remote storage method.

## Views

- `System`: end-to-end LiFi communication path.
- `TX`: transmitter GUI, serial framing, firmware, Manchester encoder, LED driver.
- `RX`: TEPT4400 receiver, ADC threshold, Manchester decoder, frame parser, RX GUI.
- `Circuit`: physical LED-to-sensor path.
- `Theory`: protocol and Manchester/FEC flow.
- `Bottleneck`: current debug focus around RX signal threshold and voltage swing.
- `Firmware Patterns`: historical churn map for RX timing, TX polarity, experimental firmware, and counterpart TX/RX matching.
- `Evolution`: repo and commit-history timeline.

Use the version selector in the toolbar to switch the diagrams between the current working tree and important older repo versions, including the known-good `4d78a01` RX baseline. Older versions show historical flow and schematic values as read-only references; the current version remains editable.

## Handoff Notes

Node comments, system comments, and schematic component edits are saved in the browser through `localStorage`.

Use `npm run app` instead of `npm run dev` when you want the planner to save comments/components into this repo automatically:

```bash
npm run app
```

Then use `Submit status`. It writes:

- `handoffs/latest.json`
- `handoffs/latest.md`
- archived snapshots in `handoffs/archive/`

The planner also polls `latest.json`, so other devices connected to the same running planner URL can update automatically.

Important limitation: this only works while the device running `npm run app` is powered on and reachable. If the device is off, use the committed repo footprint instead:

- `handoffs/PROJECT_CONTEXT.md`
- `docs/lifi_system_workflow.md`
- committed debug logs and code

The saved handoff contains:

- selected view/node
- per-node comments
- overall system comment
- schematic component names/values/notes

Future Codex sessions should read `handoffs/` first to understand project status and direction.
