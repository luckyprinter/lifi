import os
import time
import math
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import serial
import serial.tools.list_ports

BAUDRATE = 115200
DEFAULT_FREQUENCY_HZ = 9000
MIN_FREQUENCY_HZ = 1
MAX_FREQUENCY_HZ = 50000
FEC_GROUP_SIZE = 8
DEBUG_LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "debug_logs"))

THEMES = {
    "Dark": {
        "bg": "#0f172a",
        "panel": "#111827",
        "panel_alt": "#172033",
        "text": "#e5e7eb",
        "muted": "#94a3b8",
        "accent": "#38bdf8",
        "accent_dark": "#0369a1",
        "good": "#22c55e",
        "warn": "#f59e0b",
        "bad": "#ef4444",
        "field": "#020617",
        "status_bg": "#1f2937",
    },
    "Light": {
        "bg": "#eef3f8",
        "panel": "#ffffff",
        "panel_alt": "#dbe7f0",
        "text": "#172033",
        "muted": "#5d6f82",
        "accent": "#14b8c4",
        "accent_dark": "#0f7f8c",
        "good": "#168553",
        "warn": "#b7791f",
        "bad": "#c2413a",
        "field": "#f8fbfd",
        "status_bg": "#e4edf5",
    },
    "Wood": {
        "bg": "#2b2118",
        "panel": "#3b2a1d",
        "panel_alt": "#563b27",
        "text": "#f8ead2",
        "muted": "#d7b98f",
        "accent": "#f2a65a",
        "accent_dark": "#9a5a22",
        "good": "#8fc46b",
        "warn": "#f2c078",
        "bad": "#e26d5c",
        "field": "#1f160f",
        "status_bg": "#4a3322",
    },
}

KIND_TEXT = 1
KIND_IMAGE = 2
KIND_AUDIO = 3
KIND_VIDEO = 4
KIND_FILE = 5

KIND_NAMES = {
    KIND_TEXT: "text",
    KIND_IMAGE: "image",
    KIND_AUDIO: "audio",
    KIND_VIDEO: "video",
    KIND_FILE: "file",
}

DEFAULT_EXT = {
    KIND_TEXT: ".txt",
    KIND_IMAGE: ".jpg",
    KIND_AUDIO: ".mp3",
    KIND_VIDEO: ".mp4",
    KIND_FILE: ".bin",
}


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def safe_filename(name: str) -> str:
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ()"
    cleaned = "".join(c if c in keep else "_" for c in name)
    return cleaned.strip(" ._") or "received_file.bin"


def fmt_time(sec):
    if sec < 0 or math.isinf(sec):
        return "--"
    sec = int(sec)
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    return f"{m}m {s}s"


def select_all_text(widget):
    widget.focus_set()
    widget.tag_add("sel", "1.0", "end-1c")
    widget.mark_set("insert", "1.0")
    widget.see("insert")
    return "break"


def bind_text_copy_shortcuts(widget):
    widget.bind("<Control-a>", lambda _event: select_all_text(widget))
    widget.bind("<Control-A>", lambda _event: select_all_text(widget))


def padded_chunk(data: bytes, chunk_size: int) -> bytes:
    if len(data) >= chunk_size:
        return data[:chunk_size]
    return data + bytes(chunk_size - len(data))


class TransferState:
    def __init__(self, tid, kind, total_chunks, total_size, file_crc, name):
        self.tid = tid
        self.kind = kind
        self.total_chunks = total_chunks
        self.total_size = total_size
        self.file_crc = file_crc
        self.name = name
        self.chunks = {}
        self.parity_blocks = {}
        self.start_time = time.time()
        self.saved = False

    def add_chunk(self, seq, data):
        if seq in self.chunks or seq < 0 or seq >= self.total_chunks:
            return False
        self.chunks[seq] = data
        return True

    def add_parity(self, group_start, group_count, chunk_size, parity):
        self.parity_blocks[group_start] = {
            "group_count": group_count,
            "chunk_size": chunk_size,
            "parity": parity,
        }

    def received_bytes(self):
        return sum(len(x) for x in self.chunks.values())

    def complete(self):
        return len(self.chunks) == self.total_chunks

    def assemble(self):
        return b"".join(self.chunks[i] for i in range(self.total_chunks))

    def expected_chunk_len(self, seq, chunk_size):
        offset = seq * chunk_size
        remaining = self.total_size - offset
        if remaining <= 0:
            return 0
        return min(chunk_size, remaining)

    def try_recover_from_parity(self, group_start):
        block = self.parity_blocks.get(group_start)
        if not block:
            return None

        group_count = block["group_count"]
        chunk_size = block["chunk_size"]
        parity = block["parity"]
        group_end = min(self.total_chunks, group_start + group_count)
        missing = [seq for seq in range(group_start, group_end) if seq not in self.chunks]

        if len(missing) != 1 or len(parity) != chunk_size:
            return None

        recovered = bytearray(parity)
        for seq in range(group_start, group_end):
            if seq == missing[0]:
                continue
            chunk = padded_chunk(self.chunks[seq], chunk_size)
            for i, value in enumerate(chunk):
                recovered[i] ^= value

        seq = missing[0]
        real_len = self.expected_chunk_len(seq, chunk_size)
        data = bytes(recovered[:real_len])

        if self.add_chunk(seq, data):
            return seq, data

        return None


class RXGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi RX - Optical Carousel")
        self.fit_to_screen()
        self.minsize(760, 520)
        self.configure(bg="#eef3f8")

        self.ser = None
        self.running = False
        self.rx_buffer = bytearray()
        self.expecting_raw = None
        self.transfers = {}
        self.last_file = None
        self.theme_var = tk.StringVar(value="Light")
        self.stats_var = tk.StringVar(value="No RX stats yet.")
        self.capture_ms_var = tk.StringVar(value="100")
        self.capture_sample_us_var = tk.StringVar(value="10")
        self.adc_threshold_var = tk.StringVar(value="1000")
        os.makedirs(DEBUG_LOG_DIR, exist_ok=True)
        self.log_path = os.path.join(DEBUG_LOG_DIR, f"rx_gui_monitor_{time.strftime('%Y%m%d_%H%M%S')}.log")

        self.receive_folder = os.path.expanduser("~/LiFiReceived")
        os.makedirs(self.receive_folder, exist_ok=True)

        self.setup_theme(self.theme_var.get())
        self.build_ui()
        self.refresh_ports()

    def fit_to_screen(self):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1180, max(760, screen_w - 60))
        height = min(760, max(520, screen_h - 90))
        self.geometry(f"{width}x{height}")

    def setup_theme(self, theme_name):
        self.colors = THEMES.get(theme_name, THEMES["Dark"])
        self.configure(bg=self.colors["bg"])

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=self.colors["panel"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 20, "bold"))
        style.configure("PanelTitle.TLabel", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI", 12, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("Accent.TButton", background=self.colors["accent_dark"], foreground="#f8fafc")
        style.map("Accent.TButton", background=[("active", self.colors["accent"])])
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=self.colors["panel_alt"],
            background=self.colors["accent"],
            bordercolor=self.colors["panel_alt"],
            lightcolor=self.colors["accent"],
            darkcolor=self.colors["accent_dark"],
            thickness=16,
        )
        style.configure("TCombobox", fieldbackground=self.colors["field"], background=self.colors["panel_alt"], foreground=self.colors["text"], arrowcolor=self.colors["text"])

    def change_theme(self, _event=None):
        self.setup_theme(self.theme_var.get())
        self.recolor_widgets()

    def recolor_widgets(self):
        status_color = self.colors["good"] if self.ser and self.ser.is_open else self.colors["bad"]
        self.status.configure(bg=self.colors["status_bg"], fg=status_color)
        self.subtitle.configure(foreground=self.colors["muted"])
        self.debug_check.configure(
            bg=self.colors["panel"],
            fg=self.colors["text"],
            activebackground=self.colors["panel"],
            activeforeground=self.colors["text"],
            selectcolor=self.colors["field"],
        )
        self.folder_entry.configure(
            bg=self.colors["field"],
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
        )
        for widget in (self.text_out, self.log):
            widget.configure(
                bg=self.colors["field"],
                fg=self.colors["text"],
                insertbackground=self.colors["accent"],
            )
        self.configure_log_tags()

    def panel(self, parent, **grid_options):
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        frame.grid(**grid_options)
        return frame

    def build_ui(self):
        shell = ttk.Frame(self, padding=10)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(3, weight=1)

        header = ttk.Frame(shell)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="LiFi RX", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        self.subtitle = ttk.Label(header, text="Manchester light in, serial diagnostics out", foreground=self.colors["muted"])
        self.subtitle.grid(row=1, column=0, sticky="w")
        self.status = tk.Label(header, text="Disconnected", bg=self.colors["status_bg"], fg=self.colors["bad"], padx=14, pady=7)
        self.status.grid(row=0, column=1, rowspan=2, sticky="e")

        top = self.panel(shell, row=1, column=0, sticky="ew", pady=(0, 8))
        for col in range(10):
            top.columnconfigure(col, weight=0)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        ttk.Label(top, text="RX serial port", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=16)
        self.port_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 10), pady=(3, 0))

        ttk.Label(top, text="Optical frequency", style="Muted.TLabel").grid(row=0, column=2, sticky="w")
        self.freq_var = tk.StringVar(value=str(DEFAULT_FREQUENCY_HZ))
        ttk.Entry(top, textvariable=self.freq_var, width=10).grid(row=1, column=2, sticky="ew", padx=(0, 10), pady=(3, 0))

        self.debug_var = tk.BooleanVar(value=False)
        self.debug_check = tk.Checkbutton(top, text="RX Debug", variable=self.debug_var, command=self.set_debug, bg=self.colors["panel"], fg=self.colors["text"], activebackground=self.colors["panel"], activeforeground=self.colors["text"], selectcolor=self.colors["field"])
        self.debug_check.grid(row=1, column=3, sticky="w", padx=(0, 10), pady=(3, 0))

        ttk.Label(top, text="Theme", style="Muted.TLabel").grid(row=0, column=4, sticky="w")
        self.theme_box = ttk.Combobox(
            top,
            textvariable=self.theme_var,
            values=list(THEMES.keys()),
            state="readonly",
            width=8,
        )
        self.theme_box.grid(row=1, column=4, sticky="ew", padx=(0, 10), pady=(3, 0))
        self.theme_box.bind("<<ComboboxSelected>>", self.change_theme)

        ttk.Label(top, text="Capture ms", style="Muted.TLabel").grid(row=0, column=5, sticky="w")
        ttk.Entry(top, textvariable=self.capture_ms_var, width=8).grid(row=1, column=5, sticky="ew", padx=(0, 10), pady=(3, 0))

        ttk.Label(top, text="Sample us", style="Muted.TLabel").grid(row=0, column=6, sticky="w")
        ttk.Entry(top, textvariable=self.capture_sample_us_var, width=8).grid(row=1, column=6, sticky="ew", padx=(0, 10), pady=(3, 0))

        ttk.Label(top, text="ADC thresh", style="Muted.TLabel").grid(row=0, column=7, sticky="w")
        ttk.Entry(top, textvariable=self.adc_threshold_var, width=9).grid(row=1, column=7, sticky="ew", padx=(0, 10), pady=(3, 0))

        buttons = ttk.Frame(top, style="Panel.TFrame")
        buttons.grid(row=2, column=0, columnspan=10, sticky="ew", pady=(10, 0))
        self.connect_btn = ttk.Button(buttons, text="Connect", style="Accent.TButton", command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=(0, 5))
        ttk.Button(buttons, text="Refresh", command=self.refresh_ports).pack(side="left", padx=3)
        ttk.Button(buttons, text="Set Freq", command=self.set_freq).pack(side="left", padx=3)
        ttk.Button(buttons, text="RX Test", command=self.rx_test).pack(side="left", padx=3)
        ttk.Button(buttons, text="Digital Cap", command=self.rx_digital_capture).pack(side="left", padx=3)
        ttk.Button(buttons, text="ADC Cap", command=self.rx_adc_capture).pack(side="left", padx=3)
        ttk.Button(buttons, text="Stats", command=self.request_rx_stats).pack(side="left", padx=3)
        ttk.Button(buttons, text="Reset Stats", command=self.reset_rx_stats).pack(side="left", padx=3)
        ttk.Button(buttons, text="Reset Transfers", command=self.reset_transfers).pack(side="left", padx=3)

        folder = self.panel(shell, row=2, column=0, sticky="ew", pady=(0, 10))
        folder.columnconfigure(1, weight=1)
        ttk.Label(folder, text="Receive folder", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.folder_entry = tk.Entry(folder, bg=self.colors["field"], fg=self.colors["text"], insertbackground=self.colors["accent"], relief="flat")
        self.folder_entry.insert(0, self.receive_folder)
        self.folder_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 10))
        ttk.Button(folder, text="Browse", command=self.browse_folder).grid(row=1, column=2, padx=3)
        ttk.Button(folder, text="Open Folder", command=self.open_folder).grid(row=1, column=3, padx=3)
        ttk.Button(folder, text="Open Last", command=self.open_last).grid(row=1, column=4, padx=3)

        self.progress = ttk.Progressbar(folder, maximum=100)
        self.progress.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(12, 4))
        self.progress_label = ttk.Label(folder, text="0% | missing --", style="Muted.TLabel")
        self.progress_label.grid(row=3, column=0, sticky="w")
        self.stats_label = ttk.Label(folder, textvariable=self.stats_var, style="Muted.TLabel")
        self.stats_label.grid(row=3, column=1, columnspan=4, sticky="e")

        body = ttk.Frame(shell)
        body.grid(row=3, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = self.panel(body, row=0, column=0, sticky="nsew", padx=(0, 7))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        right = self.panel(body, row=0, column=1, sticky="nsew", padx=(7, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(left, text="Received Text", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.text_out = scrolledtext.ScrolledText(left, state="disabled", height=20, bg=self.colors["field"], fg=self.colors["text"], relief="flat", font=("Consolas", 10), padx=10, pady=10)
        self.text_out.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        bind_text_copy_shortcuts(self.text_out)

        log_header = ttk.Frame(right, style="Panel.TFrame")
        log_header.grid(row=0, column=0, sticky="ew")
        log_header.columnconfigure(0, weight=1)
        ttk.Label(log_header, text="RX Event Log", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(log_header, text="Copy Log", command=lambda: self.copy_widget_text(self.log, "Copied RX log")).grid(row=0, column=1, sticky="e", padx=(0, 6))
        ttk.Button(log_header, text="Save Log", command=self.save_log).grid(row=0, column=2, sticky="e", padx=(0, 6))
        ttk.Button(log_header, text="Clear Log", command=self.clear_log).grid(row=0, column=3, sticky="e")
        self.log = scrolledtext.ScrolledText(right, state="disabled", bg=self.colors["field"], fg=self.colors["text"], relief="flat", font=("Consolas", 9), padx=10, pady=10)
        self.log.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        bind_text_copy_shortcuts(self.log)
        self.configure_log_tags()

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.disconnect()
        else:
            self.connect()

    def log_msg(self, msg):
        def ui():
            tag = self.log_tag(msg)
            self.log.config(state="normal")
            timestamp = time.strftime("%H:%M:%S")
            self.log.insert(tk.END, f"{timestamp} RX: ", "time")
            self.log.insert(tk.END, f"{msg}\n", tag)
            self.log.see(tk.END)
            self.log.config(state="disabled")
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(f"{timestamp} RX: {msg}\n")
            except Exception:
                pass
        self.after(0, ui)

    def configure_log_tags(self):
        if not hasattr(self, "log"):
            return
        self.log.tag_configure("time", foreground=self.colors["muted"])
        self.log.tag_configure("info", foreground=self.colors["text"])
        self.log.tag_configure("success", foreground=self.colors["good"])
        self.log.tag_configure("warning", foreground=self.colors["warn"])
        self.log.tag_configure("error", foreground=self.colors["bad"])
        self.log.tag_configure("protocol", foreground=self.colors["accent_dark"])

    def log_tag(self, msg):
        text = msg.lower()
        if "error" in text or "fail" in text or "bad_crc" in text or "bad_header" in text:
            return "error"
        if "unstable" in text or "transitions=0" in text or "high=0" in text:
            return "warning"
        if "ok" in text or "connected" in text or "saved" in text or "framesok=" in text:
            return "success"
        if text.startswith("rx_") or "crc" in text or "chunk" in text or "parity" in text or "tid=" in text:
            return "protocol"
        return "info"

    def text_msg(self, msg):
        def ui():
            self.text_out.config(state="normal")
            self.text_out.insert(tk.END, msg + "\n")
            self.text_out.see(tk.END)
            self.text_out.config(state="disabled")
        self.after(0, ui)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_box["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set("/dev/ttyUSB0" if "/dev/ttyUSB0" in ports else ports[0])

    def connect(self):
        if self.ser and self.ser.is_open:
            self.log_msg("Already connected.")
            return

        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Port", "Select RX COM port.")
            return

        try:
            self.ser = serial.Serial(port, BAUDRATE, timeout=0.05, write_timeout=5)
        except Exception as e:
            messagebox.showerror("Serial Error", str(e))
            return

        self.running = True
        self.status.config(text=f"Connected: {port}", fg=self.colors["good"])
        self.connect_btn.config(text="Disconnect")

        threading.Thread(target=self.reader_loop, daemon=True).start()

        time.sleep(1)
        self.set_freq()
        self.set_debug()
        self.log_msg("Connected.")

    def disconnect(self, log_message=True):
        self.running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception as e:
            self.log_msg(f"Disconnect error: {e}")
        finally:
            self.ser = None
            self.connect_btn.config(text="Connect", state="normal")
            self.status.config(text="Disconnected", fg=self.colors["bad"])
            if log_message:
                self.log_msg("Disconnected.")

    def set_freq(self):
        if not self.ser or not self.ser.is_open:
            return
        try:
            freq = int(self.freq_var.get())
            if freq < MIN_FREQUENCY_HZ or freq > MAX_FREQUENCY_HZ:
                raise ValueError(f"Use {MIN_FREQUENCY_HZ}-{MAX_FREQUENCY_HZ} Hz")
            self.ser.write(f"FREQ={freq}\n".encode())
            self.ser.flush()
            self.log_msg(f"FREQ={freq}")
        except Exception as e:
            self.log_msg(f"Frequency error: {e}")

    def set_debug(self):
        if not self.ser or not self.ser.is_open:
            return
        value = 1 if self.debug_var.get() else 0
        self.ser.write(f"DEBUG={value}\n".encode())
        self.ser.flush()
        self.log_msg(f"DEBUG={value}")

    def rx_test(self):
        self.send_command("RXTEST=1000", "Requested 1s digital RX test")

    def rx_digital_capture(self):
        try:
            duration_ms = int(self.capture_ms_var.get())
            sample_us = int(self.capture_sample_us_var.get())
            if not 5 <= duration_ms <= 2000:
                raise ValueError("Capture ms must be 5-2000")
            if not 2 <= sample_us <= 1000:
                raise ValueError("Digital sample us must be 2-1000")
        except Exception as e:
            self.log_msg(f"Digital capture input error: {e}")
            return
        self.send_command(
            f"RXCAP={duration_ms},{sample_us}",
            f"Requested digital capture {duration_ms} ms @ {sample_us} us",
        )

    def rx_adc_capture(self):
        try:
            duration_ms = int(self.capture_ms_var.get())
            sample_us = int(self.capture_sample_us_var.get())
            threshold_mv = int(self.adc_threshold_var.get())
            if not 5 <= duration_ms <= 2000:
                raise ValueError("Capture ms must be 5-2000")
            if not 50 <= sample_us <= 5000:
                raise ValueError("ADC sample us must be 50-5000")
            if not 0 <= threshold_mv <= 3300:
                raise ValueError("ADC threshold must be 0-3300 mV")
        except Exception as e:
            self.log_msg(f"ADC capture input error: {e}")
            return
        self.send_command(
            f"ADCAP={duration_ms},{sample_us},{threshold_mv}",
            f"Requested ADC capture {duration_ms} ms @ {sample_us} us, threshold {threshold_mv} mV",
        )

    def request_rx_stats(self):
        self.send_command("STATS", "Requested RX stats")

    def reset_rx_stats(self):
        self.send_command("RESETSTATS", "Requested RX stats reset")

    def send_command(self, command, message):
        if not self.ser or not self.ser.is_open:
            self.log_msg("Connect RX before sending debug command.")
            return
        try:
            self.ser.write(f"{command}\n".encode())
            self.ser.flush()
            self.log_msg(message)
        except Exception as e:
            self.log_msg(f"Command error {command}: {e}")

    def reader_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                data = self.ser.read(4096)
            except Exception:
                break

            if data:
                self.rx_buffer.extend(data)
                self.process_buffer()

    def process_buffer(self):
        while True:
            if self.expecting_raw is not None:
                meta = self.expecting_raw
                needed = meta["name_len"] + meta["raw_len"]

                if len(self.rx_buffer) < needed:
                    return

                raw = bytes(self.rx_buffer[:needed])
                del self.rx_buffer[:needed]

                if self.rx_buffer.startswith(b"\r\n"):
                    del self.rx_buffer[:2]
                elif self.rx_buffer.startswith(b"\n"):
                    del self.rx_buffer[:1]

                name_bytes = raw[:meta["name_len"]]
                raw_payload = raw[meta["name_len"]:]

                name = name_bytes.decode("utf-8", errors="replace")
                self.expecting_raw = None

                if meta["frame"] == "chunk":
                    self.handle_chunk(meta, name, raw_payload)
                elif meta["frame"] == "parity":
                    self.handle_parity(meta, name, raw_payload)
                continue

            idx = self.rx_buffer.find(b"\n")
            if idx < 0:
                return

            line = bytes(self.rx_buffer[:idx + 1])
            del self.rx_buffer[:idx + 1]

            text = line.decode("utf-8", errors="replace").strip()

            if text:
                self.handle_line(text)

    def handle_line(self, line):
        if line.startswith("RX_CAROUSEL_CHUNK:"):
            try:
                parts = line.split(":")
                self.expecting_raw = {
                    "frame": "chunk",
                    "tid": int(parts[1]),
                    "kind": int(parts[2]),
                    "seq": int(parts[3]),
                    "total_chunks": int(parts[4]),
                    "total_size": int(parts[5]),
                    "chunk_len": int(parts[6]),
                    "raw_len": int(parts[6]),
                    "file_crc": int(parts[7], 16),
                    "name_len": int(parts[8]),
                }
            except Exception as e:
                self.log_msg(f"Bad chunk line: {line} / {e}")
                self.expecting_raw = None
            return

        if line.startswith("RX_CAROUSEL_PARITY:"):
            try:
                parts = line.split(":")
                self.expecting_raw = {
                    "frame": "parity",
                    "tid": int(parts[1]),
                    "kind": int(parts[2]),
                    "group_start": int(parts[3]),
                    "total_chunks": int(parts[4]),
                    "total_size": int(parts[5]),
                    "chunk_size": int(parts[6]),
                    "file_crc": int(parts[7], 16),
                    "name_len": int(parts[8]),
                    "group_count": int(parts[9]),
                    "parity_len": int(parts[10]),
                    "raw_len": int(parts[10]),
                }
            except Exception as e:
                self.log_msg(f"Bad parity line: {line} / {e}")
                self.expecting_raw = None
            return

        self.log_msg(line)
        if (
            line.startswith("RX_STATS:")
            or line.startswith("RX_DIGITAL_TEST:")
            or line.startswith("RX_DIGITAL_CAPTURE:")
            or line.startswith("RX_ADC_CAPTURE:")
        ):
            self.after(0, lambda value=line: self.stats_var.set(value))

    def get_or_create_transfer(self, tid, kind, total_chunks, total_size, file_crc, name):
        if tid not in self.transfers:
            st = TransferState(
                tid,
                kind,
                total_chunks,
                total_size,
                file_crc,
                safe_filename(name),
            )
            self.transfers[tid] = st
            self.log_msg(
                f"New transfer tid={tid}: {KIND_NAMES.get(kind, 'file')} "
                f"'{st.name}', {total_size} bytes, {total_chunks} chunks, "
                f"file_crc=0x{file_crc:04X}"
            )
            return st

        return self.transfers[tid]

    def handle_chunk(self, meta, name, data):
        tid = meta["tid"]
        kind = meta["kind"]
        seq = meta["seq"]
        total_chunks = meta["total_chunks"]
        total_size = meta["total_size"]
        file_crc = meta["file_crc"]

        st = self.get_or_create_transfer(tid, kind, total_chunks, total_size, file_crc, name)

        if st.saved:
            return

        added = st.add_chunk(seq, data)

        if added:
            self.log_msg(
                f"Stored tid={tid} chunk {seq + 1}/{st.total_chunks} "
                f"({len(data)} bytes). Missing {st.total_chunks - len(st.chunks)}"
            )
        else:
            self.log_msg(f"Duplicate tid={tid} chunk {seq + 1}/{st.total_chunks} ignored")

        self.update_progress(st)
        self.try_recover_near(st, seq)

        if st.complete() and not st.saved:
            self.finish_transfer(st)

    def handle_parity(self, meta, name, parity):
        tid = meta["tid"]
        kind = meta["kind"]
        group_start = meta["group_start"]
        total_chunks = meta["total_chunks"]
        total_size = meta["total_size"]
        chunk_size = meta["chunk_size"]
        file_crc = meta["file_crc"]
        group_count = meta["group_count"]

        st = self.get_or_create_transfer(tid, kind, total_chunks, total_size, file_crc, name)

        if st.saved:
            return

        st.add_parity(group_start, group_count, chunk_size, parity)
        self.log_msg(
            f"Stored tid={tid} parity group {group_start + 1}-"
            f"{min(total_chunks, group_start + group_count)}/{total_chunks} "
            f"({len(parity)} bytes)"
        )
        self.try_recover_near(st, group_start)
        self.update_progress(st)

        if st.complete() and not st.saved:
            self.finish_transfer(st)

    def try_recover_near(self, st, seq):
        starts = set()
        starts.add((seq // FEC_GROUP_SIZE) * FEC_GROUP_SIZE)
        starts.update(st.parity_blocks.keys())

        for group_start in sorted(starts):
            recovered = st.try_recover_from_parity(group_start)
            if recovered is None:
                continue

            recovered_seq, data = recovered
            self.log_msg(
                f"FEC recovered tid={st.tid} chunk {recovered_seq + 1}/{st.total_chunks} "
                f"({len(data)} bytes)"
            )

        if st.complete() and not st.saved:
            self.finish_transfer(st)

    def update_progress(self, st):
        done = st.received_bytes()
        pct = min(100, done * 100 / max(1, st.total_size))
        missing = st.total_chunks - len(st.chunks)

        elapsed = time.time() - st.start_time
        rate = done / elapsed if elapsed > 0 else 0
        eta = (st.total_size - done) / rate if rate > 0 else -1

        def ui():
            self.progress["value"] = pct
            self.progress_label.config(
                text=f"{pct:.1f}% | missing {missing} | ETA {fmt_time(eta)}"
            )
        self.after(0, ui)

    def finish_transfer(self, st):
        if st.saved:
            return

        try:
            data = st.assemble()
        except Exception as e:
            self.log_msg(f"Assembly failed: {e}")
            return

        actual_crc = crc16_ccitt(data)

        if len(data) != st.total_size or actual_crc != st.file_crc:
            self.log_msg(
                f"RX_FILE_REBUILD_FAIL tid={st.tid}: "
                f"len={len(data)}/{st.total_size}, "
                f"crc=0x{actual_crc:04X}, expected=0x{st.file_crc:04X}"
            )
            return

        st.saved = True

        if st.kind == KIND_TEXT:
            text = data.decode("utf-8", errors="replace")
            self.text_msg(f"--- Received text tid={st.tid} ---")
            self.text_msg(text)
            self.log_msg(f"RX_TEXT_CAROUSEL_OK tid={st.tid}")
            return

        folder = self.folder_entry.get().strip() or self.receive_folder
        os.makedirs(folder, exist_ok=True)

        name = st.name
        root, ext = os.path.splitext(name)

        if not ext:
            name = root + DEFAULT_EXT.get(st.kind, ".bin")

        path = os.path.join(folder, f"received_{int(time.time())}_{safe_filename(name)}")

        with open(path, "wb") as f:
            f.write(data)

        self.last_file = path
        self.log_msg(f"Saved file: {path}")
        self.log_msg(f"RX_FILE_CAROUSEL_OK tid={st.tid}, crc=0x{actual_crc:04X}")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder)

    def open_folder(self):
        folder = self.folder_entry.get().strip()
        if not os.path.isdir(folder):
            return
        if os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])

    def open_last(self):
        if not self.last_file or not os.path.exists(self.last_file):
            return
        if os.name == "nt":
            os.startfile(self.last_file)
        else:
            subprocess.Popen(["xdg-open", self.last_file])

    def save_log(self):
        path = filedialog.asksaveasfilename(
            initialdir=DEBUG_LOG_DIR,
            initialfile=os.path.basename(self.log_path),
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            text = self.log.get("1.0", tk.END)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.log_msg(f"Saved visible log: {path}")
        except Exception as e:
            self.log_msg(f"Save log failed: {e}")

    def clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.config(state="disabled")
        self.log_msg("Visible log cleared.")

    def copy_widget_text(self, widget, message):
        text = widget.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log_msg(message)

    def reset_transfers(self):
        self.transfers.clear()
        self.rx_buffer.clear()
        self.expecting_raw = None
        self.progress["value"] = 0
        self.progress_label.config(text="0% | missing --")
        self.log_msg("Transfers reset.")

    def on_close(self):
        self.disconnect(log_message=False)
        self.destroy()


if __name__ == "__main__":
    app = RXGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
