#!/usr/bin/env python3
"""Root launcher for the stable LiFi receiver GUI."""

from apps.stable.Rx_gui import RXGui


if __name__ == "__main__":
    app = RXGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
