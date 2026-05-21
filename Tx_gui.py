#!/usr/bin/env python3
"""Root launcher for the stable LiFi transmitter GUI."""

from apps.stable.Tx_gui import TXGui


if __name__ == "__main__":
    app = TXGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
