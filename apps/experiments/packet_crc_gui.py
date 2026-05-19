import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import serial
import serial.tools.list_ports


BAUDRATE = 115200
DEFAULT_RX_PORT = "/dev/ttyUSB0"
DEFAULT_TX_PORT = "/dev/ttyUSB1"
DEBUG_LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "debug_logs"))


def bind_select_all(widget):
    def select_all(_event):
        widget.focus_set()
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "1.0")
        return "break"

    widget.bind("<Control-a>", select_all)
    widget.bind("<Control-A>", select_all)


class SerialSide:
    def __init__(self, name, on_line, on_status):
        self.name = name
        self.on_line = on_line
        self.on_status = on_status
        self.ser = None
        self.running = False
        self.thread = None

    def connect(self, port):
        if self.ser and self.ser.is_open:
            return
        self.ser = serial.Serial(port, BAUDRATE, timeout=0.05, write_timeout=2)
        self.running = True
        self.thread = threading.Thread(target=self.reader_loop, daemon=True)
        self.thread.start()
        self.on_status(self.name, f"Connected: {port}", True)

    def disconnect(self):
        self.running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.ser = None
            self.on_status(self.name, "Disconnected", False)

    def send(self, line):
        if not self.ser or not self.ser.is_open:
            raise RuntimeError(f"{self.name} serial is not connected")
        self.ser.write((line.rstrip("\n") + "\n").encode("utf-8"))
        self.ser.flush()

    def reader_loop(self):
        buffer = bytearray()
        while self.running and self.ser and self.ser.is_open:
            try:
                ser = self.ser
                if ser is None:
                    break
                data = ser.read(512)
            except Exception as exc:
                if self.running:
                    self.on_line(self.name, f"READ_ERROR:{exc}")
                break
            if not data:
                continue
            buffer.extend(data)
            while b"\n" in buffer:
                raw, _, buffer = buffer.partition(b"\n")
                text = raw.decode("utf-8", errors="replace").rstrip("\r")
                self.on_line(self.name, text)
        self.running = False


class PacketCRCGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi Packet CRC Test")
        self.geometry("1080x680")
        self.minsize(820, 520)

        os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
        session_stamp = time.strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(DEBUG_LOG_DIR, f"packet_crc_gui_shared_{session_stamp}.log")
        self.rx_log_path = os.path.join(DEBUG_LOG_DIR, f"packet_crc_gui_rx_{session_stamp}.log")
        self.tx_log_path = os.path.join(DEBUG_LOG_DIR, f"packet_crc_gui_tx_{session_stamp}.log")

        self.rx = SerialSide("RX", self.queue_log, self.queue_status)
        self.tx = SerialSide("TX", self.queue_log, self.queue_status)

        self.rx_port = tk.StringVar(value=DEFAULT_RX_PORT)
        self.tx_port = tk.StringVar(value=DEFAULT_TX_PORT)
        self.freq = tk.StringVar(value="1000")
        self.rx_inv = tk.BooleanVar(value=True)
        self.rx_debug = tk.BooleanVar(value=True)
        self.rx_phase = tk.StringVar(value="50")
        self.data_type = tk.StringVar(value="1")
        self.message = tk.StringVar(value="1")
        self.rx_status = tk.StringVar(value="Disconnected")
        self.tx_status = tk.StringVar(value="Disconnected")

        self.build_ui()
        self.refresh_ports()

    def build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        title = ttk.Label(root, text="Packet CRC Active-High LiFi Test", font=("Segoe UI", 17, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 10))

        controls = ttk.Frame(root)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)

        rx_box = ttk.LabelFrame(controls, text="RX /dev/ttyUSB0")
        rx_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tx_box = ttk.LabelFrame(controls, text="TX /dev/ttyUSB1")
        tx_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self.build_rx_controls(rx_box)
        self.build_tx_controls(tx_box)

        terminals = ttk.PanedWindow(root, orient=tk.VERTICAL)
        terminals.grid(row=2, column=0, sticky="nsew")

        shared_box = self.terminal_box(
            terminals,
            "Shared Serial Log",
            [("Copy Shared", lambda: self.copy_widget(self.log, "Copied shared log")), ("Save Shared", lambda: self.save_widget(self.log, "shared")), ("Clear", self.clear_log)],
        )
        terminals.add(shared_box, weight=3)

        split_box = ttk.PanedWindow(terminals, orient=tk.HORIZONTAL)
        terminals.add(split_box, weight=2)

        rx_box = self.terminal_box(
            split_box,
            "RX Terminal",
            [("Copy RX", lambda: self.copy_widget(self.rx_log, "Copied RX log")), ("Save RX", lambda: self.save_widget(self.rx_log, "rx"))],
        )
        tx_box = self.terminal_box(
            split_box,
            "TX Terminal",
            [("Copy TX", lambda: self.copy_widget(self.tx_log, "Copied TX log")), ("Save TX", lambda: self.save_widget(self.tx_log, "tx"))],
        )
        split_box.add(rx_box, weight=1)
        split_box.add(tx_box, weight=1)

    def terminal_box(self, parent, title, buttons):
        box = ttk.Frame(parent)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(1, weight=1)

        head = ttk.Frame(box)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text=title, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        for idx, (label, command) in enumerate(buttons, start=1):
            ttk.Button(head, text=label, command=command).grid(row=0, column=idx, padx=(6, 0))

        widget = scrolledtext.ScrolledText(box, font=("Consolas", 9), wrap="none")
        widget.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        widget.tag_configure("RX", foreground="#0f766e")
        widget.tag_configure("TX", foreground="#1d4ed8")
        widget.tag_configure("ERR", foreground="#b91c1c")
        bind_select_all(widget)

        if title.startswith("Shared"):
            self.log = widget
        elif title.startswith("RX"):
            self.rx_log = widget
        elif title.startswith("TX"):
            self.tx_log = widget

        return box

    def build_rx_controls(self, parent):
        for col in range(6):
            parent.columnconfigure(col, weight=1 if col in (1, 3) else 0)

        ttk.Label(parent, text="Port").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.rx_ports = ttk.Combobox(parent, textvariable=self.rx_port, width=16)
        self.rx_ports.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        self.rx_connect_btn = ttk.Button(parent, text="Connect", command=self.toggle_rx)
        self.rx_connect_btn.grid(row=0, column=2, padx=6, pady=4)
        ttk.Button(parent, text="Refresh", command=self.refresh_ports).grid(row=0, column=3, padx=6, pady=4)

        ttk.Label(parent, text="Freq").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(parent, textvariable=self.freq, width=10).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(parent, text="Set RX Freq", command=self.set_rx_freq).grid(row=1, column=2, padx=6, pady=4)
        ttk.Button(parent, text="Stats", command=lambda: self.send_rx("STATS")).grid(row=1, column=3, padx=6, pady=4)

        ttk.Checkbutton(parent, text="INV", variable=self.rx_inv, command=self.set_rx_inv).grid(row=2, column=0, padx=6, pady=4)
        ttk.Checkbutton(parent, text="DEBUG", variable=self.rx_debug, command=self.set_rx_debug).grid(row=2, column=1, padx=6, pady=4)
        ttk.Label(parent, text="Phase").grid(row=2, column=2, sticky="e", padx=6, pady=4)
        ttk.Entry(parent, textvariable=self.rx_phase, width=5).grid(row=2, column=3, sticky="w", padx=6, pady=4)
        ttk.Button(parent, text="Set Phase", command=self.set_rx_phase).grid(row=2, column=4, padx=6, pady=4)
        ttk.Button(parent, text="RXCAP 2s", command=lambda: self.send_rx("RXCAP=2000,50")).grid(row=2, column=5, padx=6, pady=4)

        ttk.Button(parent, text="RXCAP 100ms", command=lambda: self.send_rx("RXCAP=100,10")).grid(row=3, column=0, padx=6, pady=4)
        ttk.Button(parent, text="Reset Stats", command=lambda: self.send_rx("RESETSTATS")).grid(row=3, column=1, padx=6, pady=4)

        ttk.Label(parent, textvariable=self.rx_status).grid(row=4, column=0, columnspan=6, sticky="w", padx=6, pady=(4, 8))

    def build_tx_controls(self, parent):
        for col in range(6):
            parent.columnconfigure(col, weight=1 if col in (1, 3) else 0)

        ttk.Label(parent, text="Port").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.tx_ports = ttk.Combobox(parent, textvariable=self.tx_port, width=16)
        self.tx_ports.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        self.tx_connect_btn = ttk.Button(parent, text="Connect", command=self.toggle_tx)
        self.tx_connect_btn.grid(row=0, column=2, padx=6, pady=4)
        ttk.Button(parent, text="Set TX Freq", command=self.set_tx_freq).grid(row=0, column=3, padx=6, pady=4)

        ttk.Label(parent, text="Type").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(parent, textvariable=self.data_type, values=["1", "2", "3"], width=6, state="readonly").grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Button(parent, text="Set Type", command=self.set_tx_type).grid(row=1, column=2, padx=6, pady=4)

        ttk.Label(parent, text="Message").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(parent, textvariable=self.message).grid(row=2, column=1, columnspan=2, sticky="ew", padx=6, pady=4)
        ttk.Button(parent, text="Send", command=self.send_message).grid(row=2, column=3, padx=6, pady=4)

        ttk.Label(parent, textvariable=self.tx_status).grid(row=3, column=0, columnspan=4, sticky="w", padx=6, pady=(4, 8))

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.rx_ports["values"] = ports
        self.tx_ports["values"] = ports
        if DEFAULT_RX_PORT in ports:
            self.rx_port.set(DEFAULT_RX_PORT)
        elif ports and not self.rx_port.get():
            self.rx_port.set(ports[0])
        if DEFAULT_TX_PORT in ports:
            self.tx_port.set(DEFAULT_TX_PORT)
        elif len(ports) > 1 and not self.tx_port.get():
            self.tx_port.set(ports[1])

    def toggle_rx(self):
        try:
            if self.rx.ser and self.rx.ser.is_open:
                self.rx.disconnect()
            else:
                self.rx.connect(self.rx_port.get().strip())
                time.sleep(0.2)
                self.set_rx_freq()
                self.set_rx_inv()
                self.set_rx_phase()
                self.set_rx_debug()
        except Exception as exc:
            messagebox.showerror("RX Serial", str(exc))

    def toggle_tx(self):
        try:
            if self.tx.ser and self.tx.ser.is_open:
                self.tx.disconnect()
            else:
                self.tx.connect(self.tx_port.get().strip())
                time.sleep(0.2)
                self.set_tx_freq()
                self.set_tx_type()
        except Exception as exc:
            messagebox.showerror("TX Serial", str(exc))

    def set_rx_freq(self):
        self.send_rx(f"FREQ={self.freq.get().strip()}")

    def set_tx_freq(self):
        self.send_tx(f"FREQ={self.freq.get().strip()}")

    def set_rx_inv(self):
        self.send_rx(f"INV={1 if self.rx_inv.get() else 0}")

    def set_rx_debug(self):
        self.send_rx(f"DEBUG={1 if self.rx_debug.get() else 0}")

    def set_rx_phase(self):
        self.send_rx(f"PHASE={self.rx_phase.get().strip() or '50'}")

    def set_tx_type(self):
        self.send_tx(f"TYPE={self.data_type.get().strip()}")

    def send_message(self):
        self.set_tx_type()
        self.send_tx(f"SEND={self.message.get()}")

    def send_rx(self, line):
        self.send_side(self.rx, line)

    def send_tx(self, line):
        self.send_side(self.tx, line)

    def send_side(self, side, line):
        try:
            side.send(line)
            self.queue_log(side.name, f"> {line}")
        except Exception as exc:
            self.queue_log(side.name, f"SEND_ERROR:{exc}")

    def queue_status(self, side, status, ok):
        var = self.rx_status if side == "RX" else self.tx_status
        button = self.rx_connect_btn if side == "RX" else self.tx_connect_btn

        def update():
            var.set(status)
            button.configure(text="Disconnect" if ok else "Connect")

        self.after(0, update)

    def queue_log(self, side, text):
        self.after(0, lambda: self.add_log(side, text))

    def add_log(self, side, text):
        timestamp = time.strftime("%H:%M:%S")
        tag = "ERR" if "ERROR" in text or "FAIL" in text else side
        line = f"{timestamp} {side}: {text}\n"
        self.append_to_widget(self.log, side, tag, timestamp, text)
        if side == "RX":
            self.append_to_widget(self.rx_log, side, tag, timestamp, text)
        elif side == "TX":
            self.append_to_widget(self.tx_log, side, tag, timestamp, text)

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
            side_path = self.rx_log_path if side == "RX" else self.tx_log_path
            with open(side_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def append_to_widget(self, widget, side, tag, timestamp, text):
        widget.insert(tk.END, f"{timestamp} {side}: ", side)
        widget.insert(tk.END, f"{text}\n", tag)
        widget.see(tk.END)

    def copy_widget(self, widget, message):
        text = widget.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.add_log("TX", message)

    def save_widget(self, widget, label):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(DEBUG_LOG_DIR, f"packet_crc_{label}_copy_{stamp}.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(widget.get("1.0", "end-1c"))
            f.write("\n")
        self.add_log("TX", f"Saved {label} log copy: {path}")

    def clear_log(self):
        self.log.delete("1.0", tk.END)

    def destroy(self):
        self.rx.disconnect()
        self.tx.disconnect()
        super().destroy()


if __name__ == "__main__":
    PacketCRCGui().mainloop()
