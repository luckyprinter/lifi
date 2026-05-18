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

## Views

- `System`: end-to-end LiFi communication path.
- `TX`: transmitter GUI, serial framing, firmware, Manchester encoder, LED driver.
- `RX`: TEPT4400 receiver, ADC threshold, Manchester decoder, frame parser, RX GUI.
- `Circuit`: physical LED-to-sensor path.
- `Theory`: protocol and Manchester/FEC flow.
- `Bottleneck`: current debug focus around RX signal threshold and voltage swing.
- `Evolution`: repo and commit-history timeline.

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
