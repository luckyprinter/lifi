import os
import time
import math
import struct
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    from .serial_utils import build_port_choices, extract_device, friendly_serial_error, open_serial
except ImportError:
    from serial_utils import build_port_choices, extract_device, friendly_serial_error, open_serial

BAUDRATE = 115200
START_BYTE = 0x02
TYPE_CAROUSEL_CHUNK = 0x20
TYPE_CAROUSEL_PARITY = 0x21
DEFAULT_FREQUENCY_HZ = 9000
MIN_FREQUENCY_HZ = 1
MAX_FREQUENCY_HZ = 50000
DEFAULT_CHUNK_SIZE = 512
DEFAULT_CAROUSEL_ROUNDS = 2
DEFAULT_ROUND_GAP_MS = 250
DEFAULT_INTER_FRAME_GAP_MS = 0
DEFAULT_WAIT_TX_DONE = False
FEC_GROUP_SIZE = 8
MAX_FRAME_PAYLOAD = 65535
MAX_TOTAL_CHUNKS = 65535
FUTURE_TARGET_FILE_SIZE = 1024 * 1024

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


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def safe_name(name: str) -> str:
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ()"
    return "".join(c if c in keep else "_" for c in name)[:80] or "file.bin"


def fmt_time(sec):
    if sec < 0 or math.isinf(sec):
        return "--"
    sec = int(sec)
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    return f"{m}m {s}s"


def fmt_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


def padded_chunk(data: bytes, chunk_size: int) -> bytes:
    if len(data) >= chunk_size:
        return data[:chunk_size]
    return data + bytes(chunk_size - len(data))


def build_xor_parity(chunks, chunk_size: int) -> bytes:
    parity = bytearray(chunk_size)
    for chunk in chunks:
        padded = padded_chunk(chunk, chunk_size)
        for i, value in enumerate(padded):
            parity[i] ^= value
    return bytes(parity)


class TXGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi TX - Optical Carousel")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(bg="#eef3f8")

        self.ser = None
        self.running = False
        self.transfer_running = False
        self.tx_done = threading.Event()
        self.theme_var = tk.StringVar(value="Light")
        self.fec_var = tk.BooleanVar(value=True)
        self.wait_done_var = tk.BooleanVar(value=DEFAULT_WAIT_TX_DONE)
        self.port_map = {}

        self.setup_theme(self.theme_var.get())
        self.build_ui()
        self.refresh_ports()

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
        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 7))
        style.configure("Accent.TButton", background=self.colors["accent_dark"], foreground="#f8fafc")
        style.map("Accent.TButton", background=[("active", self.colors["accent"])])
        style.configure("Danger.TButton", foreground=self.colors["bad"])
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
        self.fec_check.configure(
            bg=self.colors["panel"],
            fg=self.colors["text"],
            activebackground=self.colors["panel"],
            activeforeground=self.colors["text"],
            selectcolor=self.colors["field"],
        )
        self.wait_done_check.configure(
            bg=self.colors["panel"],
            fg=self.colors["text"],
            activebackground=self.colors["panel"],
            activeforeground=self.colors["text"],
            selectcolor=self.colors["field"],
        )
        for widget in (self.text_box, self.log):
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
        shell = ttk.Frame(self, padding=18)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(3, weight=1)

        header = ttk.Frame(shell)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="LiFi TX", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        self.subtitle = ttk.Label(header, text="Serial control in, Manchester light out", foreground=self.colors["muted"])
        self.subtitle.grid(row=1, column=0, sticky="w")
        self.status = tk.Label(header, text="Disconnected", bg=self.colors["status_bg"], fg=self.colors["bad"], padx=14, pady=7)
        self.status.grid(row=0, column=1, rowspan=2, sticky="e")

        top = self.panel(shell, row=1, column=0, sticky="ew", pady=(0, 10))
        for col in range(13):
            top.columnconfigure(col, weight=0)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(5, weight=1)

        ttk.Label(top, text="TX serial port", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=16)
        self.port_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 10), pady=(3, 0))

        ttk.Label(top, text="Optical frequency", style="Muted.TLabel").grid(row=0, column=2, sticky="w")
        self.freq_var = tk.StringVar(value=str(DEFAULT_FREQUENCY_HZ))
        ttk.Entry(top, textvariable=self.freq_var, width=10).grid(row=1, column=2, sticky="ew", padx=(0, 10), pady=(3, 0))

        ttk.Label(top, text="Chunk bytes", style="Muted.TLabel").grid(row=0, column=3, sticky="w")
        self.chunk_var = tk.StringVar(value=str(DEFAULT_CHUNK_SIZE))
        ttk.Combobox(
            top,
            textvariable=self.chunk_var,
            values=["256", "512", "1024", "2048"],
            width=7,
            state="readonly",
        ).grid(row=1, column=3, sticky="ew", padx=(0, 10), pady=(3, 0))

        ttk.Label(top, text="Carousel rounds", style="Muted.TLabel").grid(row=0, column=4, sticky="w")
        self.rounds_var = tk.StringVar(value=str(DEFAULT_CAROUSEL_ROUNDS))
        ttk.Entry(top, textvariable=self.rounds_var, width=8).grid(row=1, column=4, sticky="ew", padx=(0, 10), pady=(3, 0))

        ttk.Label(top, text="Round gap ms", style="Muted.TLabel").grid(row=0, column=5, sticky="w")
        self.gap_var = tk.StringVar(value=str(DEFAULT_ROUND_GAP_MS))
        ttk.Entry(top, textvariable=self.gap_var, width=10).grid(row=1, column=5, sticky="ew", padx=(0, 12), pady=(3, 0))

        ttk.Label(top, text="Theme", style="Muted.TLabel").grid(row=0, column=6, sticky="w")
        self.theme_box = ttk.Combobox(
            top,
            textvariable=self.theme_var,
            values=list(THEMES.keys()),
            state="readonly",
            width=8,
        )
        self.theme_box.grid(row=1, column=6, sticky="ew", padx=(0, 10), pady=(3, 0))
        self.theme_box.bind("<<ComboboxSelected>>", self.change_theme)

        ttk.Label(top, text="Frame gap ms", style="Muted.TLabel").grid(row=0, column=7, sticky="w")
        self.frame_gap_var = tk.StringVar(value=str(DEFAULT_INTER_FRAME_GAP_MS))
        ttk.Entry(top, textvariable=self.frame_gap_var, width=8).grid(row=1, column=7, sticky="ew", padx=(0, 10), pady=(3, 0))

        self.connect_btn = ttk.Button(top, text="Connect", style="Accent.TButton", command=self.toggle_connection)
        self.connect_btn.grid(row=1, column=8, padx=3, pady=(3, 0))
        ttk.Button(top, text="Refresh", command=self.refresh_ports).grid(row=1, column=9, padx=3, pady=(3, 0))
        ttk.Button(top, text="Set Freq", command=self.set_freq).grid(row=1, column=10, padx=3, pady=(3, 0))
        self.fec_check = tk.Checkbutton(
            top,
            text="FEC",
            variable=self.fec_var,
            bg=self.colors["panel"],
            fg=self.colors["text"],
            activebackground=self.colors["panel"],
            activeforeground=self.colors["text"],
            selectcolor=self.colors["field"],
        )
        self.fec_check.grid(row=1, column=11, padx=3, pady=(3, 0))

        progress_panel = self.panel(shell, row=2, column=0, sticky="ew", pady=(0, 10))
        progress_panel.columnconfigure(0, weight=1)
        ttk.Label(progress_panel, text="Optical carousel progress", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.stop_btn = ttk.Button(progress_panel, text="Stop", style="Danger.TButton", command=self.stop_transfer, state="disabled")
        self.stop_btn.grid(row=0, column=1, sticky="e")
        self.progress = ttk.Progressbar(progress_panel, maximum=100)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        self.progress_label = ttk.Label(progress_panel, text="0% | ETA --", style="Muted.TLabel")
        self.progress_label.grid(row=2, column=0, sticky="w")
        self.wait_done_check = tk.Checkbutton(
            progress_panel,
            text="Wait for TX done marker",
            variable=self.wait_done_var,
            command=self.update_transmission_mode_label,
            bg=self.colors["panel"],
            fg=self.colors["text"],
            activebackground=self.colors["panel"],
            activeforeground=self.colors["text"],
            selectcolor=self.colors["field"],
        )
        self.wait_done_check.grid(row=2, column=1, sticky="e")
        self.mode_label = ttk.Label(progress_panel, text="", style="Muted.TLabel")
        self.mode_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.update_transmission_mode_label()

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

        ttk.Label(left, text="Payload", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.text_box = scrolledtext.ScrolledText(left, height=10, bg=self.colors["field"], fg=self.colors["text"], insertbackground=self.colors["accent"], relief="flat", font=("Segoe UI", 10), padx=10, pady=10)
        self.text_box.grid(row=1, column=0, sticky="nsew", pady=(8, 10))

        btns = ttk.Frame(left, style="Panel.TFrame")
        btns.grid(row=2, column=0, sticky="ew")

        ttk.Button(btns, text="Send Text", style="Accent.TButton", command=self.send_text).pack(side="left", padx=(0, 5))
        ttk.Button(btns, text="Image", command=lambda: self.send_file(KIND_IMAGE)).pack(side="left", padx=3)
        ttk.Button(btns, text="Audio", command=lambda: self.send_file(KIND_AUDIO)).pack(side="left", padx=3)
        ttk.Button(btns, text="Video", command=lambda: self.send_file(KIND_VIDEO)).pack(side="left", padx=3)

        log_header = ttk.Frame(right, style="Panel.TFrame")
        log_header.grid(row=0, column=0, sticky="ew")
        log_header.columnconfigure(0, weight=1)
        ttk.Label(log_header, text="TX Event Log", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(log_header, text="Clear Log", command=self.clear_log).grid(row=0, column=1, sticky="e")

        self.log = scrolledtext.ScrolledText(
            right,
            state="disabled",
            bg=self.colors["field"],
            fg=self.colors["text"],
            relief="flat",
            font=("JetBrains Mono", 9),
            padx=12,
            pady=10,
            spacing1=2,
            spacing3=4,
        )
        self.log.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.configure_log_tags()

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.disconnect()
        else:
            self.connect()

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
        if "error" in text or "fail" in text or "bad_crc" in text or "denied" in text:
            return "error"
        if "warn" in text or "unstable" in text or "timeout" in text:
            return "warning"
        if "ok" in text or "done" in text or "connected" in text or "sent in" in text:
            return "success"
        if "tx_" in text or "crc" in text or "frame" in text or "chunk" in text or "parity" in text:
            return "protocol"
        return "info"

    def log_msg(self, msg):
        def ui():
            tag = self.log_tag(msg)
            self.log.config(state="normal")
            self.log.insert(tk.END, time.strftime("%H:%M:%S"), ("time",))
            self.log.insert(tk.END, "  TX  ", ("time",))
            self.log.insert(tk.END, f"{msg}\n", (tag,))
            self.log.see(tk.END)
            self.log.config(state="disabled")
        self.after(0, ui)

    def clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.config(state="disabled")

    def update_transmission_mode_label(self):
        if not hasattr(self, "mode_label"):
            return

        if self.wait_done_var.get():
            text = "Transmission mode: Debug wait mode"
        else:
            text = "Transmission mode: Smooth streaming mode"

        self.mode_label.config(text=text)
        self.set_tx_quiet_mode()

    def refresh_ports(self):
        labels, mapping = build_port_choices()
        self.port_map = mapping
        self.port_box["values"] = labels
        if labels and (not self.port_var.get() or self.port_var.get() not in mapping):
            self.port_var.set(labels[0])
        elif not labels:
            self.port_var.set("")
            self.log_msg("No likely ESP32 USB serial ports found. Plug in the board and press Refresh.")

    def connect(self):
        if self.ser and self.ser.is_open:
            self.log_msg("Already connected.")
            return

        selection = self.port_var.get().strip()
        port = extract_device(selection, self.port_map)
        if not port:
            messagebox.showwarning("Port", "Select TX COM port.")
            return

        try:
            self.ser = open_serial(port, BAUDRATE, timeout=0.05, write_timeout=5)
        except Exception as e:
            message = friendly_serial_error(port, e)
            self.log_msg(message.replace("\n", " | "))
            messagebox.showerror("Serial Error", message)
            return

        self.running = True
        self.port_var.set(selection)
        self.status.config(text=f"Connected: {port}", fg=self.colors["good"])
        self.connect_btn.config(text="Disconnect")
        threading.Thread(target=self.reader_loop, daemon=True).start()

        time.sleep(1)
        self.set_freq()
        self.set_tx_quiet_mode()
        self.log_msg("Connected.")

    def disconnect(self, log_message=True):
        self.running = False
        self.transfer_running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception as e:
            self.log_msg(f"Disconnect error: {e}")
        finally:
            self.ser = None
            self.connect_btn.config(text="Connect", state="normal")
            self.stop_btn.config(state="disabled")
            self.status.config(text="Disconnected", fg=self.colors["bad"])
            if log_message:
                self.log_msg("Disconnected.")

    def reader_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline()
            except Exception:
                break

            if not line:
                continue

            text = line.decode(errors="replace").strip()
            if text:
                self.log_msg(text)
                if text.startswith("TX_CAROUSEL_FRAME_SENT"):
                    self.tx_done.set()

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

    def set_tx_quiet_mode(self):
        if not self.ser or not self.ser.is_open:
            return

        quiet = 0 if self.wait_done_var.get() else 1

        try:
            self.ser.write(f"QUIET={quiet}\n".encode())
            self.ser.flush()
            self.log_msg("Debug wait mode" if quiet == 0 else "Smooth streaming mode")
        except Exception as e:
            self.log_msg(f"TX mode error: {e}")

    def stop_transfer(self):
        self.transfer_running = False
        self.log_msg("Stopping after current frame...")

    def send_text(self):
        text = self.text_box.get("1.0", "end-1c")
        if not text.strip():
            return
        if not text.endswith("\n"):
            text += "\n"
        self.start_transfer(text.encode("utf-8"), KIND_TEXT, "text_message.txt")

    def send_file(self, kind):
        if kind == KIND_IMAGE:
            ft = [("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"), ("All files", "*.*")]
        elif kind == KIND_AUDIO:
            ft = [("Audio", "*.mp3 *.wav *.m4a *.aac *.ogg *.flac"), ("All files", "*.*")]
        elif kind == KIND_VIDEO:
            ft = [("Video", "*.mp4 *.webm *.avi *.mov *.mkv"), ("All files", "*.*")]
        else:
            ft = [("All files", "*.*")]

        path = filedialog.askopenfilename(filetypes=ft)
        if not path:
            return

        with open(path, "rb") as f:
            data = f.read()

        self.start_transfer(data, kind, os.path.basename(path))

    def start_transfer(self, data, kind, filename):
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("Serial", "Connect TX first.")
            return

        if self.transfer_running:
            messagebox.showwarning("Busy", "Transfer already running.")
            return

        if not data:
            messagebox.showwarning("Empty Payload", "Choose or enter data before starting the light transfer.")
            return

        self.transfer_running = True
        self.stop_btn.config(state="normal")
        threading.Thread(target=self.transfer_worker, args=(data, kind, filename), daemon=True).start()

    def read_transfer_settings(self):
        try:
            chunk_size = int(self.chunk_var.get())
            rounds = int(self.rounds_var.get())
            gap_ms = int(self.gap_var.get())
            frame_gap_ms = int(self.frame_gap_var.get())
        except ValueError as exc:
            raise ValueError("Chunk, rounds, round gap, and frame gap must be whole numbers.") from exc

        if chunk_size <= 0:
            raise ValueError("Chunk size must be greater than zero.")
        if rounds <= 0:
            raise ValueError("Rounds must be greater than zero.")
        if gap_ms < 0:
            raise ValueError("Round gap cannot be negative.")
        if frame_gap_ms < 0:
            raise ValueError("Frame gap cannot be negative.")

        return chunk_size, rounds, gap_ms / 1000.0, frame_gap_ms / 1000.0

    def transfer_worker(self, data, kind, filename):
        try:
            chunk_size, rounds, gap, frame_gap = self.read_transfer_settings()
        except ValueError as e:
            self.after(0, lambda: messagebox.showerror("Transfer Settings", str(e)))
            self.transfer_running = False
            self.after(0, lambda: self.stop_btn.config(state="disabled"))
            return

        wait_for_done = self.wait_done_var.get()
        self.set_tx_quiet_mode()

        file_crc = crc16_ccitt(data)
        name = safe_name(filename).encode("utf-8")
        total_size = len(data)
        total_chunks = (total_size + chunk_size - 1) // chunk_size
        if total_size >= FUTURE_TARGET_FILE_SIZE:
            self.log_msg(
                "Large file mode: this protocol can chunk 1 MB-class files, "
                "but transfer time and missed chunks will depend on optical alignment."
            )

        if total_chunks <= 0:
            self.log_msg("Nothing to send.")
            self.transfer_running = False
            self.after(0, lambda: self.stop_btn.config(state="disabled"))
            return

        if total_chunks > MAX_TOTAL_CHUNKS:
            self.after(0, lambda: messagebox.showerror("Transfer Settings", "This file needs more than 65535 chunks. Use a larger chunk size."))
            self.transfer_running = False
            self.after(0, lambda: self.stop_btn.config(state="disabled"))
            return

        if 16 + len(name) + chunk_size > MAX_FRAME_PAYLOAD:
            self.after(0, lambda: messagebox.showerror("Transfer Settings", "Frame payload exceeds 65535 bytes. Use a smaller chunk size or shorter filename."))
            self.transfer_running = False
            self.after(0, lambda: self.stop_btn.config(state="disabled"))
            return

        if self.fec_var.get() and 19 + len(name) + chunk_size > MAX_FRAME_PAYLOAD:
            self.after(0, lambda: messagebox.showerror("Transfer Settings", "Parity frame exceeds 65535 bytes. Use a smaller chunk size or shorter filename."))
            self.transfer_running = False
            self.after(0, lambda: self.stop_btn.config(state="disabled"))
            return

        tid = random.randint(1, 65535)

        fec_enabled = self.fec_var.get()
        parity_groups = math.ceil(total_chunks / FEC_GROUP_SIZE) if fec_enabled else 0
        total_frames = (total_chunks + parity_groups) * rounds
        sent_frames = 0
        try:
            freq = int(self.freq_var.get())
        except ValueError:
            freq = DEFAULT_FREQUENCY_HZ
        estimated_payload_bytes = 0
        for seq in range(total_chunks):
            offset = seq * chunk_size
            estimated_payload_bytes += 16 + len(name) + len(data[offset:offset + chunk_size])
        if fec_enabled:
            estimated_payload_bytes += parity_groups * (19 + len(name) + chunk_size)
        estimated_optical_bytes = (total_chunks + parity_groups) * (32 + 1 + 1 + 2 + 2) + estimated_payload_bytes
        estimated_one_round = estimated_optical_bytes * 10 / max(1, freq)
        estimated_all_rounds = estimated_one_round * rounds

        self.log_msg(
            f"Carousel start: {KIND_NAMES[kind]} '{filename}', "
            f"tid={tid}, size={fmt_bytes(total_size)}, chunks={total_chunks}, "
            f"chunk={chunk_size}, rounds={rounds}, fec={'on' if fec_enabled else 'off'}, "
            f"mode={'debug wait' if wait_for_done else 'smooth streaming'}, "
            f"file_crc=0x{file_crc:04X}"
        )
        self.log_msg(
            f"Estimated optical time: {fmt_time(estimated_one_round)} per round, "
            f"{fmt_time(estimated_all_rounds)} total at {freq} Hz"
        )

        start = time.time()

        for r in range(rounds):
            if not self.transfer_running:
                break

            self.log_msg(f"Round {r + 1}/{rounds} start")

            for group_start in range(0, total_chunks, FEC_GROUP_SIZE):
                if not self.transfer_running:
                    break

                group_chunks = []
                group_end = min(total_chunks, group_start + FEC_GROUP_SIZE)

                for seq in range(group_start, group_end):
                    if not self.transfer_running:
                        break

                    offset = seq * chunk_size
                    chunk = data[offset:offset + chunk_size]
                    group_chunks.append(chunk)

                    payload_len = self.send_chunk(
                        tid,
                        kind,
                        seq,
                        total_chunks,
                        total_size,
                        file_crc,
                        name,
                        chunk,
                        log_detail=wait_for_done,
                    )

                    self.pace_after_frame(payload_len, wait_for_done, frame_gap)
                    sent_frames = self.mark_frame_progress(sent_frames, total_frames, start, wait_for_done)

                if fec_enabled and self.transfer_running and group_chunks:
                    parity_len = self.send_parity_chunk(
                        tid,
                        kind,
                        group_start,
                        total_chunks,
                        total_size,
                        chunk_size,
                        file_crc,
                        name,
                        group_chunks,
                        log_detail=wait_for_done,
                    )

                    self.pace_after_frame(parity_len, wait_for_done, frame_gap)
                    sent_frames = self.mark_frame_progress(sent_frames, total_frames, start, wait_for_done)

            if r != rounds - 1 and gap > 0:
                time.sleep(gap)

        self.transfer_running = False
        self.after(0, lambda: self.stop_btn.config(state="disabled"))
        elapsed_total = time.time() - start
        self.after(0, lambda e=elapsed_total: self.update_progress_done(e))
        self.log_msg(f"Carousel done: sent {sent_frames}/{total_frames} frames in {fmt_time(elapsed_total)}")

    def mark_frame_progress(self, sent_frames, total_frames, start, verbose=False):
        sent_frames += 1
        pct = sent_frames * 100 / max(1, total_frames)

        elapsed = time.time() - start
        rate = sent_frames / elapsed if elapsed > 0 else 0
        remain = (total_frames - sent_frames) / rate if rate > 0 else -1

        should_update = verbose or sent_frames == 1 or sent_frames == total_frames or sent_frames % 8 == 0

        if should_update:
            self.after(0, lambda p=pct, rm=remain: self.update_progress(p, rm))

        return sent_frames

    def update_progress(self, pct, remain):
        self.progress["value"] = pct
        self.progress_label.config(text=f"{pct:.1f}% | ETA {fmt_time(remain)}")

    def update_progress_done(self, elapsed):
        self.progress["value"] = 100
        self.progress_label.config(text=f"100% | sent in {fmt_time(elapsed)}")

    def send_chunk(self, tid, kind, seq, total_chunks, total_size, file_crc, name, chunk, log_detail=False):
        real_len = len(chunk)

        payload = struct.pack(
            ">HBHHIHHB",
            tid,
            kind,
            seq,
            total_chunks,
            total_size,
            real_len,
            file_crc,
            len(name),
        ) + name + chunk

        frame_crc = self.send_frame(TYPE_CAROUSEL_CHUNK, payload)

        if log_detail:
            self.log_msg(
                f"Sent tid={tid} chunk {seq + 1}/{total_chunks} "
                f"({real_len} bytes), frame_crc=0x{frame_crc:04X}"
            )

        return len(payload)

    def send_parity_chunk(self, tid, kind, group_start, total_chunks, total_size, chunk_size, file_crc, name, chunks, log_detail=False):
        parity = build_xor_parity(chunks, chunk_size)
        group_count = len(chunks)

        payload = struct.pack(
            ">HBHHIHHBBH",
            tid,
            kind,
            group_start,
            total_chunks,
            total_size,
            chunk_size,
            file_crc,
            len(name),
            group_count,
            len(parity),
        ) + name + parity

        frame_crc = self.send_frame(TYPE_CAROUSEL_PARITY, payload)

        if log_detail:
            self.log_msg(
                f"Sent tid={tid} parity group {group_start + 1}-"
                f"{group_start + group_count}/{total_chunks} "
                f"({len(parity)} bytes), frame_crc=0x{frame_crc:04X}"
            )

        return len(payload)

    def send_frame(self, frame_type, payload):
        frame_crc = crc16_ccitt(payload)

        header = bytes([
            START_BYTE,
            frame_type,
            (len(payload) >> 8) & 0xFF,
            len(payload) & 0xFF,
            (frame_crc >> 8) & 0xFF,
            frame_crc & 0xFF,
        ])

        self.tx_done.clear()
        self.ser.write(header + payload)
        self.ser.flush()

        return frame_crc

    def frame_airtime_seconds(self, payload_len):
        try:
            freq = int(self.freq_var.get())
        except Exception:
            freq = DEFAULT_FREQUENCY_HZ

        optical_bytes = 32 + 1 + 1 + 2 + 2 + payload_len
        return optical_bytes * 10 / max(1, freq)

    def pace_after_frame(self, payload_len, wait_for_done, extra_gap):
        if wait_for_done:
            self.wait_tx_done(payload_len)
        else:
            time.sleep(self.frame_airtime_seconds(payload_len))

        if extra_gap > 0:
            time.sleep(extra_gap)

    def wait_tx_done(self, payload_len):
        try:
            freq = int(self.freq_var.get())
        except Exception:
            freq = DEFAULT_FREQUENCY_HZ

        optical_bytes = 32 + 1 + 1 + 2 + 2 + payload_len
        ideal = optical_bytes * 10 / max(1, freq)
        timeout = max(3.0, ideal * 3 + 1)

        return self.tx_done.wait(timeout=timeout)

    def on_close(self):
        self.disconnect(log_message=False)
        self.destroy()


if __name__ == "__main__":
    app = TXGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
