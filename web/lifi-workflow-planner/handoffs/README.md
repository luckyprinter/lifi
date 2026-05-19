# Planner Handoffs

When the LiFi workflow planner is run with:

```bash
npm run app
```

the `Submit status` action saves the current planner context here:

- `latest.json` - machine-readable notes, active view, selected node, and schematic component values
- `latest.md` - human-readable summary for Codex and thesis/debug sessions
- `archive/` - timestamped snapshots when the submit button is used

Future Codex sessions should read this folder to understand the current project direction, comments, component edits, and bottleneck notes.

## Latest RX Test Note

- `debug_logs/rx_gui_monitor_20260519_133207.log` shows the `4d78a` GPIO5 digital RX baseline did not receive valid logic from the current RX circuit.
- Digital test result: `high=0`, `low=19238`, `transitions=0`.
- User measured RX node: idle light ON about `0.01 V`, transmission about `0.4 V` to `1.5 V`.
- Direction: use comparator/Schmitt/TIA cleanup for GPIO5 digital RX, or return to GPIO34 ADC threshold mode with better sampling.
