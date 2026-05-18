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
