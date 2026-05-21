#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    import serial
    import serial.tools.list_ports
except ImportError as exc:
    raise SystemExit("Missing pyserial. Install with: python3 -m pip install pyserial") from exc


BAUDRATE = 115200
DEFAULT_RX_PORT = "/dev/ttyUSB0"
DEFAULT_TX_PORT = "/dev/ttyUSB1"
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(ROOT_DIR, "logs")
TOOLS_BIN_DIR = os.path.join(ROOT_DIR, "tools", "bin")
LOCAL_ARDUINO_CLI = os.path.join(TOOLS_BIN_DIR, "arduino-cli.exe" if os.name == "nt" else "arduino-cli")
CLI_INSTALLER = os.path.join(ROOT_DIR, "tools", "install_arduino_cli.py")
DEFAULT_FQBN = "esp32:esp32:esp32doit-devkit-v1"
DEFAULT_RX_SKETCH = os.path.join(ROOT_DIR, "firmware", "rx_text_debug")
DEFAULT_TX_SKETCH = os.path.join(ROOT_DIR, "firmware", "tx_text_debug")


def bind_select_all(widget):
    def select_all(_event):
        widget.focus_set()
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "1.0")
        return "break"

    widget.bind("<Control-a>", select_all)
    widget.bind("<Control-A>", select_all)


def now():
    return time.strftime("%H:%M:%S")


class SerialEndpoint:
    def __init__(self, name, on_line, on_status):
        self.name = name
        self.on_line = on_line
        self.on_status = on_status
        self.ser = None
        self.thread = None
        self.running = False
        self.port = ""

    def connected(self):
        return self.ser is not None and self.ser.is_open

    def connect(self, port):
        if self.connected():
            return
        self.port = port
        self.ser = serial.Serial(port, BAUDRATE, timeout=0.05, write_timeout=2)
        self.running = True
        self.thread = threading.Thread(target=self.reader_loop, daemon=True)
        self.thread.start()
        self.on_status(self.name, f"connected {port}", True)

    def disconnect(self):
        self.running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.ser = None
            self.on_status(self.name, "disconnected", False)

    def send(self, line):
        if not self.connected():
            raise RuntimeError(f"{self.name} is not connected")
        payload = (line.rstrip("\n") + "\n").encode("utf-8")
        self.ser.write(payload)
        self.ser.flush()

    def reader_loop(self):
        buffer = bytearray()
        while self.running and self.connected():
            try:
                chunk = self.ser.read(512)
            except Exception as exc:
                if self.running:
                    self.on_line(self.name, f"SERIAL_READ_ERROR:{exc}")
                break
            if not chunk:
                continue
            buffer.extend(chunk)
            while b"\n" in buffer:
                raw, _, buffer = buffer.partition(b"\n")
                text = raw.decode("utf-8", errors="replace").rstrip("\r")
                self.on_line(self.name, text)
        self.running = False


class LifiTextDebugGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi Text Rebuild Debugger")
        self.geometry("1220x760")
        self.minsize(920, 600)

        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.shared_log_path = os.path.join(LOG_DIR, f"text_rebuild_shared_{stamp}.log")
        self.rx_log_path = os.path.join(LOG_DIR, f"text_rebuild_rx_{stamp}.log")
        self.tx_log_path = os.path.join(LOG_DIR, f"text_rebuild_tx_{stamp}.log")

        self.rx = SerialEndpoint("RX", self.queue_line, self.queue_status)
        self.tx = SerialEndpoint("TX", self.queue_line, self.queue_status)

        self.rx_port = tk.StringVar(value=DEFAULT_RX_PORT)
        self.tx_port = tk.StringVar(value=DEFAULT_TX_PORT)
        self.frequency = tk.StringVar(value="1000")
        self.message = tk.StringVar(value="hello")
        self.rx_inv = tk.BooleanVar(value=False)
        self.tx_inv = tk.BooleanVar(value=False)
        self.debug_bits = tk.BooleanVar(value=True)
        self.debug_bytes = tk.BooleanVar(value=True)
        self.fqbn = tk.StringVar(value=DEFAULT_FQBN)
        self.rx_sketch = tk.StringVar(value=DEFAULT_RX_SKETCH)
        self.tx_sketch = tk.StringVar(value=DEFAULT_TX_SKETCH)
        self.cli_path = tk.StringVar(value="")
        self.cli_status = tk.StringVar(value="Arduino CLI: checking...")

        self.rx_bit_stream = ""
        self.rx_byte_stream = []
        self.packet_status = tk.StringVar(value="No packet yet")
        self.packet_detail = tk.StringVar(value="Connect RX/TX, set frequency, then send text.")
        self.rx_logic = tk.StringVar(value="RX logic: --")
        self.rx_counts = tk.StringVar(value="bits 0 | bytes 0 | ok 0 | fail 0 | unstable 0")
        self.tx_status = tk.StringVar(value="TX disconnected")
        self.rx_status = tk.StringVar(value="RX disconnected")

        self.build_style()
        self.build_ui()
        self.refresh_ports()

    def build_style(self):
        self.colors = {
            "bg": "#eef3f8",
            "panel": "#ffffff",
            "panel_alt": "#e1ebf2",
            "ink": "#162f3a",
            "muted": "#617583",
            "accent": "#0f7f8c",
            "good": "#168553",
            "warn": "#b7791f",
            "bad": "#c2413a",
            "field": "#f8fbfd",
        }
        self.configure(bg=self.colors["bg"])
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["ink"], font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=self.colors["panel"], foreground=self.colors["ink"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.colors["panel"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=self.colors["bg"], foreground=self.colors["ink"], font=("Segoe UI", 20, "bold"))
        style.configure("CardTitle.TLabel", background=self.colors["panel"], foreground=self.colors["ink"], font=("Segoe UI", 12, "bold"))
        style.configure("TButton", padding=(10, 7), font=("Segoe UI", 10))
        style.configure("Accent.TButton", background=self.colors["accent"], foreground="#ffffff")
        style.configure("Danger.TButton", foreground=self.colors["bad"])
        style.configure("TCheckbutton", background=self.colors["panel"], foreground=self.colors["ink"])
        style.configure("TEntry", fieldbackground=self.colors["field"])
        style.configure("TCombobox", fieldbackground=self.colors["field"])

    def build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="LiFi Text Rebuild Debugger", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="text-first | binary-visible | CRC checked | packaging-ready later", foreground=self.colors["muted"]).grid(row=1, column=0, sticky="w")

        controls = ttk.Frame(root)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        self.build_rx_controls(controls)
        self.build_tx_controls(controls)

        upload = ttk.Frame(root, style="Panel.TFrame", padding=10)
        upload.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.build_upload_controls(upload)

        dashboard = ttk.Frame(root, style="Panel.TFrame", padding=10)
        dashboard.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        for col in range(4):
            dashboard.columnconfigure(col, weight=1)
        self.status_card(dashboard, 0, "Packet Status", self.packet_status)
        self.status_card(dashboard, 1, "Meaning", self.packet_detail)
        self.status_card(dashboard, 2, "RX Logic", self.rx_logic)
        self.status_card(dashboard, 3, "RX Counters", self.rx_counts)

        body = ttk.PanedWindow(root, orient=tk.VERTICAL)
        body.grid(row=4, column=0, sticky="nsew")

        bit_frame = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        body.add(bit_frame, weight=2)
        bit_frame.add(self.text_panel(bit_frame, "Live RX Bits", "bits"), weight=2)
        bit_frame.add(self.text_panel(bit_frame, "Decoded RX Bytes", "bytes"), weight=1)

        log_frame = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        body.add(log_frame, weight=3)
        log_frame.add(self.text_panel(log_frame, "Shared Log", "shared"), weight=2)
        log_frame.add(self.text_panel(log_frame, "RX Log", "rxlog"), weight=1)
        log_frame.add(self.text_panel(log_frame, "TX Log", "txlog"), weight=1)

    def status_card(self, parent, column, title, var):
        card = ttk.Frame(parent, style="Panel.TFrame", padding=10)
        card.grid(row=0, column=column, sticky="nsew", padx=5)
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=var, style="Panel.TLabel", wraplength=250).pack(anchor="w", pady=(6, 0))

    def text_panel(self, parent, title, kind):
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=8)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        head = ttk.Frame(frame, style="Panel.TFrame")
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text=title, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(head, text="Copy", command=lambda: self.copy_text(kind)).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(head, text="Clear", command=lambda: self.clear_text(kind)).grid(row=0, column=2, padx=(6, 0))

        widget = scrolledtext.ScrolledText(frame, wrap="word", height=8, font=("Consolas", 10), bg="#fbfdfe", fg=self.colors["ink"])
        widget.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        widget.tag_configure("RX", foreground="#0f766e")
        widget.tag_configure("TX", foreground="#1d4ed8")
        widget.tag_configure("CLI", foreground="#7c3aed")
        widget.tag_configure("OK", foreground=self.colors["good"])
        widget.tag_configure("FAIL", foreground=self.colors["bad"])
        widget.tag_configure("WARN", foreground=self.colors["warn"])
        bind_select_all(widget)

        setattr(self, f"{kind}_text", widget)
        return frame

    def build_rx_controls(self, parent):
        frame = ttk.LabelFrame(parent, text="RX / receiver")
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        for col in range(6):
            frame.columnconfigure(col, weight=1 if col in (1, 4) else 0)

        ttk.Label(frame, text="Port").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.rx_ports = ttk.Combobox(frame, textvariable=self.rx_port, width=18)
        self.rx_ports.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        self.rx_button = ttk.Button(frame, text="Connect", command=self.toggle_rx)
        self.rx_button.grid(row=0, column=2, padx=6, pady=4)
        ttk.Button(frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=3, padx=6, pady=4)
        ttk.Label(frame, textvariable=self.rx_status).grid(row=0, column=4, columnspan=2, sticky="w", padx=6, pady=4)

        ttk.Checkbutton(frame, text="Invert RX", variable=self.rx_inv, command=self.apply_rx_settings).grid(row=1, column=0, padx=6, pady=4)
        ttk.Checkbutton(frame, text="Bits", variable=self.debug_bits, command=self.apply_rx_settings).grid(row=1, column=1, padx=6, pady=4)
        ttk.Checkbutton(frame, text="Bytes", variable=self.debug_bytes, command=self.apply_rx_settings).grid(row=1, column=2, padx=6, pady=4)
        ttk.Button(frame, text="RXCAP 1s", command=lambda: self.send_rx("RXCAP=1000,50")).grid(row=1, column=3, padx=6, pady=4)
        ttk.Button(frame, text="Stats", command=lambda: self.send_rx("STATS")).grid(row=1, column=4, padx=6, pady=4)
        ttk.Button(frame, text="Reset", command=self.reset_rx_view).grid(row=1, column=5, padx=6, pady=4)

    def build_tx_controls(self, parent):
        frame = ttk.LabelFrame(parent, text="TX / transmitter")
        frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        for col in range(7):
            frame.columnconfigure(col, weight=1 if col in (1, 5) else 0)

        ttk.Label(frame, text="Port").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.tx_ports = ttk.Combobox(frame, textvariable=self.tx_port, width=18)
        self.tx_ports.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        self.tx_button = ttk.Button(frame, text="Connect", command=self.toggle_tx)
        self.tx_button.grid(row=0, column=2, padx=6, pady=4)
        ttk.Checkbutton(frame, text="Invert TX", variable=self.tx_inv, command=self.apply_tx_settings).grid(row=0, column=3, padx=6, pady=4)
        ttk.Label(frame, textvariable=self.tx_status).grid(row=0, column=4, columnspan=3, sticky="w", padx=6, pady=4)

        ttk.Label(frame, text="Freq").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.frequency, width=8).grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Button(frame, text="Set Both", command=self.set_frequency).grid(row=1, column=2, padx=6, pady=4)
        ttk.Button(frame, text="LED On", command=lambda: self.send_tx("LED=1")).grid(row=1, column=3, padx=6, pady=4)
        ttk.Button(frame, text="LED Off", command=lambda: self.send_tx("LED=0")).grid(row=1, column=4, padx=6, pady=4)
        ttk.Button(frame, text="Raw 0x55", command=lambda: self.send_tx("RAW=55")).grid(row=1, column=5, padx=6, pady=4)

        ttk.Label(frame, text="Text").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ttk.Entry(frame, textvariable=self.message).grid(row=2, column=1, columnspan=4, sticky="ew", padx=6, pady=4)
        ttk.Button(frame, text="Send Text", style="Accent.TButton", command=self.send_text).grid(row=2, column=5, padx=6, pady=4)

    def build_upload_controls(self, parent):
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)
        ttk.Label(parent, text="Firmware Upload", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(parent, textvariable=self.cli_status, style="Panel.TLabel").grid(row=0, column=1, columnspan=3, sticky="w")
        ttk.Button(parent, text="Refresh CLI", command=self.refresh_cli_status).grid(row=0, column=4, padx=6)
        ttk.Button(parent, text="Install CLI", command=self.install_arduino_cli).grid(row=0, column=5, padx=6)

        ttk.Label(parent, text="CLI path", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=self.cli_path).grid(row=1, column=1, columnspan=3, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(parent, text="Browse", command=self.choose_cli).grid(row=1, column=4, padx=6, pady=(8, 0))

        ttk.Label(parent, text="FQBN", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=self.fqbn).grid(row=2, column=1, sticky="ew", padx=6, pady=(8, 0))
        ttk.Label(parent, text="Use esp32:esp32:esp32doit-devkit-v1 unless your board differs.", style="Muted.TLabel").grid(row=2, column=2, columnspan=4, sticky="w", pady=(8, 0))

        ttk.Label(parent, text="RX sketch", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=self.rx_sketch).grid(row=3, column=1, columnspan=3, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(parent, text="Browse", command=lambda: self.choose_sketch(self.rx_sketch)).grid(row=3, column=4, padx=6, pady=(8, 0))
        ttk.Button(parent, text="Compile RX", command=lambda: self.compile_sketch("RX")).grid(row=3, column=5, padx=6, pady=(8, 0))
        ttk.Button(parent, text="Upload RX", command=lambda: self.upload_sketch("RX")).grid(row=3, column=6, padx=6, pady=(8, 0))

        ttk.Label(parent, text="TX sketch", style="Panel.TLabel").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=self.tx_sketch).grid(row=4, column=1, columnspan=3, sticky="ew", padx=6, pady=(8, 0))
        ttk.Button(parent, text="Browse", command=lambda: self.choose_sketch(self.tx_sketch)).grid(row=4, column=4, padx=6, pady=(8, 0))
        ttk.Button(parent, text="Compile TX", command=lambda: self.compile_sketch("TX")).grid(row=4, column=5, padx=6, pady=(8, 0))
        ttk.Button(parent, text="Upload TX", command=lambda: self.upload_sketch("TX")).grid(row=4, column=6, padx=6, pady=(8, 0))
        self.refresh_cli_status()

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

    def find_arduino_cli(self):
        manual = self.cli_path.get().strip()
        if manual and os.path.exists(manual):
            return manual
        if os.path.exists(LOCAL_ARDUINO_CLI):
            return LOCAL_ARDUINO_CLI
        return shutil.which("arduino-cli")

    def refresh_cli_status(self):
        cli = self.find_arduino_cli()
        if cli:
            if not self.cli_path.get().strip() or not os.path.exists(self.cli_path.get().strip()):
                self.cli_path.set(cli)
            self.cli_status.set(f"Arduino CLI: {cli}")
        else:
            self.cli_status.set("Arduino CLI: not found. Click Install CLI or use Arduino IDE.")

    def choose_cli(self):
        selected = filedialog.askopenfilename(
            title="Choose arduino-cli executable",
            filetypes=[("Arduino CLI", "arduino-cli*"), ("All files", "*.*")],
            initialdir=TOOLS_BIN_DIR if os.path.isdir(TOOLS_BIN_DIR) else ROOT_DIR,
        )
        if selected:
            self.cli_path.set(selected)
            self.refresh_cli_status()

    def choose_sketch(self, target_var):
        selected = filedialog.askopenfilename(
            title="Choose Arduino .ino sketch",
            filetypes=[("Arduino sketch", "*.ino"), ("All files", "*.*")],
            initialdir=ROOT_DIR,
        )
        if not selected:
            return
        folder = os.path.dirname(selected)
        sketch_name = os.path.splitext(os.path.basename(selected))[0]
        folder_name = os.path.basename(folder)
        if sketch_name != folder_name:
            messagebox.showinfo(
                "Arduino sketch folder",
                "Arduino CLI expects the sketch folder and main .ino to have the same name.\n\n"
                f"Selected file: {os.path.basename(selected)}\n"
                f"Using folder: {folder}\n\n"
                "If compile fails, put the .ino inside a folder with the same name.",
            )
        target_var.set(folder)

    def compile_sketch(self, side):
        sketch = self.rx_sketch.get() if side == "RX" else self.tx_sketch.get()
        cli = self.find_arduino_cli()
        if not cli:
            self.cli_missing_message()
            return
        cmd = [cli, "compile", "--fqbn", self.fqbn.get().strip(), sketch]
        self.run_cli_command(side, cmd)

    def upload_sketch(self, side):
        sketch = self.rx_sketch.get() if side == "RX" else self.tx_sketch.get()
        port = self.rx_port.get().strip() if side == "RX" else self.tx_port.get().strip()
        endpoint = self.rx if side == "RX" else self.tx
        cli = self.find_arduino_cli()
        if not cli:
            self.cli_missing_message()
            return
        if endpoint.connected():
            endpoint.disconnect()
            self.log("CLI", f"{side} serial disconnected before upload so the port is free.")
        cmd = [cli, "upload", "-p", port, "--fqbn", self.fqbn.get().strip(), sketch]
        self.run_cli_command(side, cmd)

    def install_arduino_cli(self):
        if not os.path.exists(CLI_INSTALLER):
            messagebox.showerror("Installer missing", f"Installer not found:\n{CLI_INSTALLER}")
            return
        cmd = [sys.executable, CLI_INSTALLER]
        self.run_cli_command("CLI", cmd, after=self.refresh_cli_status)

    def cli_missing_message(self):
        messagebox.showwarning(
            "Arduino CLI not found",
            "Arduino CLI was not found in this experiment folder or system PATH.\n\n"
            "Click Install CLI in the GUI, or install Arduino CLI manually, or upload using Arduino IDE.",
        )

    def run_cli_command(self, side, cmd, after=None):
        def worker():
            self.after(0, lambda: self.log("CLI", "$ " + " ".join(f'"{x}"' if " " in x else x for x in cmd)))
            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=ROOT_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                )
                assert process.stdout is not None
                for line in process.stdout:
                    self.after(0, lambda text=line.rstrip("\n"): self.log("CLI", text))
                code = process.wait()
            except Exception as exc:
                self.after(0, lambda: self.log("CLI", f"CLI_ERROR:{exc}"))
                return
            self.after(0, lambda: self.log("CLI", f"{side} command exited with code {code}"))
            if after:
                self.after(0, after)

        threading.Thread(target=worker, daemon=True).start()

    def toggle_rx(self):
        try:
            if self.rx.connected():
                self.rx.disconnect()
            else:
                self.rx.connect(self.rx_port.get().strip())
                self.rx_button.configure(text="Disconnect")
                self.after(250, self.apply_rx_settings)
                self.after(350, lambda: self.send_rx(f"FREQ={self.frequency.get()}"))
        except Exception as exc:
            messagebox.showerror("RX serial error", str(exc))

    def toggle_tx(self):
        try:
            if self.tx.connected():
                self.tx.disconnect()
            else:
                self.tx.connect(self.tx_port.get().strip())
                self.tx_button.configure(text="Disconnect")
                self.after(250, self.apply_tx_settings)
                self.after(350, lambda: self.send_tx(f"FREQ={self.frequency.get()}"))
        except Exception as exc:
            messagebox.showerror("TX serial error", str(exc))

    def apply_rx_settings(self):
        self.send_rx(f"INV={1 if self.rx_inv.get() else 0}", quiet=True)
        self.send_rx(f"DEBUGBITS={1 if self.debug_bits.get() else 0}", quiet=True)
        self.send_rx(f"DEBUGBYTES={1 if self.debug_bytes.get() else 0}", quiet=True)

    def apply_tx_settings(self):
        self.send_tx(f"INV={1 if self.tx_inv.get() else 0}", quiet=True)

    def set_frequency(self):
        text = self.frequency.get().strip()
        self.send_rx(f"FREQ={text}", quiet=True)
        self.send_tx(f"FREQ={text}", quiet=True)

    def send_text(self):
        text = self.message.get()
        self.packet_status.set("Sending")
        self.packet_detail.set(f"TX is sending {len(text)} text byte(s). Waiting for RX packet result.")
        self.send_tx(f"SEND={text}")

    def send_rx(self, line, quiet=False):
        try:
            self.rx.send(line)
            if not quiet:
                self.log("RX", f"> {line}")
        except Exception as exc:
            if not quiet:
                messagebox.showwarning("RX not connected", str(exc))

    def send_tx(self, line, quiet=False):
        try:
            self.tx.send(line)
            if not quiet:
                self.log("TX", f"> {line}")
        except Exception as exc:
            if not quiet:
                messagebox.showwarning("TX not connected", str(exc))

    def queue_status(self, side, text, connected):
        self.after(0, lambda: self.update_status(side, text, connected))

    def update_status(self, side, text, connected):
        if side == "RX":
            self.rx_status.set(f"RX {text}")
            self.rx_button.configure(text="Disconnect" if connected else "Connect")
        else:
            self.tx_status.set(f"TX {text}")
            self.tx_button.configure(text="Disconnect" if connected else "Connect")

    def queue_line(self, side, line):
        self.after(0, lambda: self.handle_line(side, line))

    def handle_line(self, side, line):
        self.log(side, line)
        if side == "RX":
            self.parse_rx_line(line)

    def parse_rx_line(self, line):
        if line.startswith("RX_BIT:"):
            bit = line.rsplit(":", 1)[-1].strip()
            if bit in ("0", "1"):
                self.rx_bit_stream += bit
                if len(self.rx_bit_stream) > 4096:
                    self.rx_bit_stream = self.rx_bit_stream[-4096:]
                self.set_text(self.bits_text, self.group_bits(self.rx_bit_stream))
            return

        if line.startswith("RX_BYTE:"):
            match = re.match(r"RX_BYTE:(0x[0-9A-Fa-f]{2}):([01]{8})", line)
            if match:
                self.rx_byte_stream.append(f"{match.group(1)} {match.group(2)}")
                self.rx_byte_stream = self.rx_byte_stream[-300:]
                self.set_text(self.bytes_text, "\n".join(self.rx_byte_stream))
            return

        if line.startswith("RX_PACKET_OK:"):
            self.packet_status.set("Success")
            self.packet_detail.set(self.explain_packet_ok(line))
            return

        if line.startswith("RX_PACKET_FAIL:"):
            self.packet_status.set("Failure")
            self.packet_detail.set(self.explain_packet_fail(line))
            return

        if line.startswith("RX_PACKET_INCOMPLETE:"):
            self.packet_status.set("Incomplete")
            self.packet_detail.set("RX saw a packet start but the stop byte or expected ending was broken.")
            return

        if line.startswith("RX_BIT_BAD:"):
            self.packet_status.set("Unstable bit")
            self.packet_detail.set("A Manchester bit had matching halves, so RX could not trust it. Check threshold, polarity, phase, or frequency.")
            return

        if line.startswith("RXCAP:"):
            self.rx_logic.set(self.compact_capture(line))
            return

        if line.startswith("RX_STATS:"):
            self.rx_counts.set(self.compact_stats(line))
            return

    def explain_packet_ok(self, line):
        text_match = re.search(r":text=(.*)$", line)
        length = self.field(line, "len")
        crc = self.field(line, "crc")
        text = text_match.group(1) if text_match else ""
        return f"CRC matched. len={length}, crc={crc}, text='{text}'"

    def explain_packet_fail(self, line):
        if "crc" in line:
            expected = self.field(line, "expected")
            got = self.field(line, "got")
            return f"CRC mismatch. Expected {expected}, got {got}. Bits arrived but at least one byte was corrupted."
        if "len_too_large" in line:
            return "Length field was corrupted into an impossible payload size."
        return line

    def compact_capture(self, line):
        samples = self.field(line, "samples")
        high = self.field(line, "high")
        low = self.field(line, "low")
        transitions = self.field(line, "transitions")
        bits = self.field(line, "bits")
        if len(bits) > 64:
            bits = bits[:64] + "..."
        return f"samples {samples} | high {high} | low {low} | transitions {transitions} | {bits}"

    def compact_stats(self, line):
        return (
            f"bits {self.field(line, 'bits')} | bytes {self.field(line, 'bytes')} | "
            f"ok {self.field(line, 'ok')} | fail {self.field(line, 'fail')} | unstable {self.field(line, 'unstable')}"
        )

    def field(self, line, name):
        match = re.search(rf"{re.escape(name)}=([^:]+)", line)
        return match.group(1) if match else "--"

    def group_bits(self, bits):
        groups = [bits[i:i + 8] for i in range(0, len(bits), 8)]
        return " ".join(groups[-160:])

    def log(self, side, line):
        tag = "OK" if "_OK" in line else "FAIL" if "_FAIL" in line or "_BAD" in line else "WARN" if "WARN" in line or "INCOMPLETE" in line else side
        text = f"{now()} {side}: {line}\n"
        for widget in (self.shared_text,):
            widget.insert("end", text, tag)
            widget.see("end")
        target = self.rxlog_text if side == "RX" else self.txlog_text
        target.insert("end", text, tag)
        target.see("end")
        self.append_file(self.shared_log_path, text)
        self.append_file(self.rx_log_path if side == "RX" else self.tx_log_path, text)

    def append_file(self, path, text):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)

    def copy_text(self, kind):
        widget = getattr(self, f"{kind}_text")
        text = widget.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)

    def clear_text(self, kind):
        widget = getattr(self, f"{kind}_text")
        widget.delete("1.0", "end")
        if kind == "bits":
            self.rx_bit_stream = ""
        elif kind == "bytes":
            self.rx_byte_stream = []

    def set_text(self, widget, text):
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.see("end")

    def reset_rx_view(self):
        self.rx_bit_stream = ""
        self.rx_byte_stream = []
        self.bits_text.delete("1.0", "end")
        self.bytes_text.delete("1.0", "end")
        self.packet_status.set("Reset")
        self.packet_detail.set("RX view cleared. Firmware stats reset requested.")
        self.send_rx("RESET", quiet=True)

    def on_close(self):
        self.rx.disconnect()
        self.tx.disconnect()
        self.destroy()


def main():
    app = LifiTextDebugGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
