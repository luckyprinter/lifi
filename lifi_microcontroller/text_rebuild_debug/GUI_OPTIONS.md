# GUI Options For The LiFi Debug Tool

The current experiment uses `tkinter` first, but the project is not locked into it.

## Recommended Now: Python Tkinter + PySerial

Best for the current debugging stage.

Pros:

- Included with most Python installs.
- Very fast to edit while firmware is changing.
- Easy serial-port handling with `pyserial`.
- Easy to package later with PyInstaller.
- Works offline on Linux and Windows.

Cons:

- Visual polish is limited compared with Qt/web apps.
- Custom plotting/widgets take more manual work.

Packaging later:

```bash
python3 -m pip install pyinstaller pyserial
pyinstaller --onefile experiments/text_rebuild/gui/lifi_text_debug_gui.py
```

## Best Polished Desktop Upgrade: PySide6 / Qt

Good when the protocol is stable and the thesis demo needs a more professional desktop app.

Pros:

- Better responsive layouts and custom widgets.
- Easier to make polished dashboards.
- Good Windows `.exe` and Linux builds through PyInstaller or Nuitka.

Cons:

- Larger dependency.
- Slower iteration while firmware is still changing.

## Good Cross-Platform App Option: Tauri

Good later if the workflow planner and serial GUI should feel like one modern app.

Pros:

- Modern HTML/CSS UI.
- Smaller than Electron.
- Can build desktop installers.

Cons:

- Serial access requires extra native/plugin work.
- More project complexity than needed for current RX/TX debugging.

## Browser/Web Serial Option

Good for Chrome-based demos on one machine.

Pros:

- UI can share style with the existing web planner.
- No desktop install for supported browsers.

Cons:

- Web Serial is browser/OS dependent.
- Harder to package as a normal offline `.exe`.
- Android serial support is not the same as desktop Chrome.

## Electron

Useful but probably too heavy for this thesis tool unless the app becomes strongly web-based.

## Decision

Use `tkinter` for the first reliable text rebuild. Move to PySide6 or Tauri only after the firmware protocol is stable and the debugging signals are known.
