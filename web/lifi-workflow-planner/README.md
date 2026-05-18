# LiFi Workflow Planner

Interactive React diagram app for explaining the LiFi thesis system flow.

## Run

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

