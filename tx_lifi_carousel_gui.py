import os
import sys
import time
import math
import random
import struct
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import serial
import serial.tools.list_ports

BAUDRATE = 115200
START_BYTE = 0x02
TYPE_CAROUSEL_CHUNK = 0x20

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
    cleaned = "".join(ch if ch in keep else "_" for ch in name)
    return (cleaned.strip(" ._") or "lifi_file.bin")[:80]


def format_duration(seconds: float) -> str:
    if seconds is None or seconds < 0 or math.isinf(seconds):
        return "--"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


class LiFiTXCarouselGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi TX - One-Way Carousel Transfer")
        self.geometry("1080x720")

        self.tx_serial = None
        self.running = False
        self.transfer_running = False
        self.tx_reader_thread = None
        self.tx_done_event = threading.Event()

        self.create_widgets()
        self.populate_ports()

    def create_widgets(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=8)

        tk.Label(toolbar, text="TX Port:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(toolbar, width=18, textvariable=self.port_var)
        self.port_combo.grid(row=0, column=1, padx=4)

        tk.Label(toolbar, text="Freq Hz:").grid(row=0, column=2, sticky="e")
        self.freq_var = tk.StringVar(value="10000")
        self.freq_entry = tk.Entry(toolbar, width=9, textvariable=self.freq_var)
        self.freq_entry.grid(row=0, column=3, padx=4)
        self.freq_entry.bind("<Return>", lambda _e: self.apply_frequency())
        tk.Button(toolbar, text="Set Freq", command=self.apply_frequency).grid(row=0, column=4, padx=4)

        tk.Label(toolbar, text="Chunk:").grid(row=0, column=5, sticky="e")
        self.chunk_var = tk.StringVar(value="512")
        ttk.Combobox(toolbar, width=7, textvariable=self.chunk_var, values=["256", "512", "1024", "2048"], state="readonly").grid(row=0, column=6, padx=4)

        tk.Label(toolbar, text="Rounds:").grid(row=0, column=7, sticky="e")
        self.rounds_var = tk.StringVar(value="3")
        tk.Entry(toolbar, width=5, textvariable=self.rounds_var).grid(row=0, column=8, padx=4)

        tk.Label(toolbar, text="Round gap ms:").grid(row=0, column=9, sticky="e")
        self.round_gap_var = tk.StringVar(value="500")
        tk.Entry(toolbar, width=6, textvariable=self.round_gap_var).grid(row=0, column=10, padx=4)

        self.connect_button = tk.Button(toolbar, text="Connect", command=self.connect_port)
        self.connect_button.grid(row=0, column=11, padx=8)
        tk.Button(toolbar, text="Refresh", command=self.refresh_ports).grid(row=0, column=12, padx=4)

        status = tk.Frame(self)
        status.pack(fill="x", padx=10, pady=4)
        self.tx_status = tk.Label(status, text="TX: Disconnected", fg="red")
        self.tx_status.pack(side="left")
        self.transfer_status = tk.Label(status, text="Idle", fg="blue")
        self.transfer_status.pack(side="left", padx=20)
        self.stop_button = tk.Button(status, text="Stop Transfer", command=self.stop_transfer, state="disabled")
        self.stop_button.pack(side="right")

        progress_frame = tk.Frame(self)
        progress_frame.pack(fill="x", padx=10, pady=4)
        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.progress_label = tk.Label(progress_frame, text="0% | ETA --", width=30)
        self.progress_label.pack(side="right")

        content = tk.Frame(self)
        content.pack(fill="both", expand=True, padx=10, pady=8)
        left = tk.Frame(content)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = tk.Frame(content)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        tk.Label(left, text="Send Text", font=("Arial", 12, "bold")).pack(anchor="w")
        self.text_box = scrolledtext.ScrolledText(left, height=10)
        self.text_box.pack(fill="x", pady=4)

        buttons = tk.Frame(left)
        buttons.pack(fill="x", pady=4)
        tk.Button(buttons, text="Broadcast Text", command=self.send_text).pack(side="left", padx=3)
        tk.Button(buttons, text="Broadcast Image", command=lambda: self.send_file_dialog(KIND_IMAGE)).pack(side="left", padx=3)
        tk.Button(buttons, text="Broadcast Audio", command=lambda: self.send_file_dialog(KIND_AUDIO)).pack(side="left", padx=3)
        tk.Button(buttons, text="Broadcast Video", command=lambda: self.send_file_dialog(KIND_VIDEO)).pack(side="left", padx=3)
        tk.Button(buttons, text="Broadcast Any File", command=lambda: self.send_file_dialog(KIND_FILE)).pack(side="left", padx=3)

        help_text = (
            "Carousel mode sends all chunks repeatedly.\n"
            "RX stores valid chunks and ignores corrupted duplicates.\n"
            "No Wi-Fi/Bluetooth and no reverse ACK channel needed."
        )
        tk.Label(left, text=help_text, justify="left", fg="#444").pack(anchor="w", pady=6)

        top = tk.Frame(right)
        top.pack(fill="x")
        tk.Label(top, text="TX Log", font=("Arial", 12, "bold")).pack(side="left")
        tk.Button(top, text="Clear", command=self.clear_log).pack(side="right")
        self.log = scrolledtext.ScrolledText(right, state="disabled", height=34, bg="#f7f7f7")
        self.log.pack(fill="both", expand=True, pady=4)

    def safe_ui(self, fn, *args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            fn(*args, **kwargs)
        else:
            self.after(0, lambda: fn(*args, **kwargs))

    def add_log(self, message: str):
        self.safe_ui(self._append_log, message)

    def _append_log(self, message: str):
        self.log.configure(state="normal")
        self.log.insert(tk.END, f"{time.strftime('%H:%M:%S')} TX: {message}\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def set_status(self, text: str, color="blue"):
        self.safe_ui(self.transfer_status.config, text=text, fg=color)

    def set_progress(self, sent_frames: int, total_frames: int, sent_bytes: int, total_bytes_rounds: int, start: float):
        pct = 0 if total_frames <= 0 else min(100.0, sent_frames * 100.0 / total_frames)
        elapsed = max(0.001, time.time() - start)
        rate = sent_bytes / elapsed if sent_bytes > 0 else 0
        remain = (total_bytes_rounds - sent_bytes) / rate if rate > 0 else -1
        def apply():
            self.progress["value"] = pct
            self.progress_label.config(text=f"{pct:5.1f}% | ETA {format_duration(remain)}")
        self.safe_ui(apply)

    def get_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def populate_ports(self):
        ports = self.get_ports()
        self.port_combo["values"] = ports
        if ports and (not self.port_var.get() or self.port_var.get() not in ports):
            self.port_var.set(ports[0])

    def refresh_ports(self):
        self.populate_ports()
        ports = self.get_ports()
        messagebox.showinfo("Serial Ports", "Detected ports:\n\n" + ("\n".join(ports) if ports else "No ports found"))

    def connect_port(self):
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Missing port", "Select TX serial port.")
            return
        try:
            self.tx_serial = serial.Serial(port, BAUDRATE, timeout=0.05, write_timeout=5)
        except Exception as e:
            messagebox.showerror("Connection failed", str(e))
            return
        self.running = True
        self.tx_status.config(text=f"TX: {port}", fg="green")
        self.connect_button.config(text="Disconnect", command=self.disconnect_port)
        self.set_status("Waiting for ESP32 boot/reset...", "orange")
        def boot():
            time.sleep(2.3)
            try:
                self.tx_serial.reset_input_buffer()
            except Exception:
                pass
            self.tx_reader_thread = threading.Thread(target=self.reader_loop, daemon=True)
            self.tx_reader_thread.start()
            self.apply_frequency()
            self.set_status("Connected", "green")
            self.add_log("Connected. One-way carousel TX ready.")
        threading.Thread(target=boot, daemon=True).start()

    def disconnect_port(self):
        self.running = False
        self.transfer_running = False
        try:
            if self.tx_serial and self.tx_serial.is_open:
                self.tx_serial.close()
        except Exception:
            pass
        self.tx_status.config(text="TX: Disconnected", fg="red")
        self.connect_button.config(text="Connect", command=self.connect_port)
        self.set_status("Idle", "blue")
        self.add_log("Disconnected.")

    def reader_loop(self):
        while self.running and self.tx_serial and self.tx_serial.is_open:
            try:
                line = self.tx_serial.readline()
            except Exception as e:
                self.add_log(f"Serial read error: {e}")
                break
            if line:
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    self.add_log(text)
                    if text.startswith("TX_CAROUSEL_FRAME_SENT"):
                        self.tx_done_event.set()
        self.add_log("TX serial monitor stopped.")

    def apply_frequency(self):
        try:
            freq = int(self.freq_var.get().strip())
        except ValueError:
            messagebox.showwarning("Invalid frequency", "Enter 1 to 50000 Hz.")
            return
        if not 1 <= freq <= 50000:
            messagebox.showwarning("Invalid frequency", "Frequency must be 1 to 50000 Hz.")
            return
        if self.tx_serial and self.tx_serial.is_open:
            try:
                self.tx_serial.write(f"FREQ={freq}\n".encode("ascii"))
                self.tx_serial.flush()
                self.add_log(f"Sent TX frequency command: FREQ={freq}")
            except Exception as e:
                self.add_log(f"Failed to set frequency: {e}")

    def ensure_connected(self) -> bool:
        if not self.tx_serial or not self.tx_serial.is_open:
            messagebox.showwarning("Not connected", "Connect TX port first.")
            return False
        if self.transfer_running:
            messagebox.showwarning("Transfer running", "Wait or press Stop Transfer first.")
            return False
        return True

    def get_chunk_size(self):
        try:
            return max(64, min(4096, int(self.chunk_var.get())))
        except Exception:
            return 512

    def get_rounds(self):
        try:
            return max(1, min(1000, int(self.rounds_var.get())))
        except Exception:
            return 3

    def get_round_gap(self):
        try:
            return max(0, min(60000, int(self.round_gap_var.get()))) / 1000.0
        except Exception:
            return 0.5

    def send_text(self):
        if not self.ensure_connected():
            return
        text = self.text_box.get("1.0", "end-1c")
        if not text.strip():
            return
        if not text.endswith("\n"):
            text += "\n"
        self.start_broadcast(text.encode("utf-8"), KIND_TEXT, "text_message.txt")

    def send_file_dialog(self, kind: int):
        if not self.ensure_connected():
            return
        if kind == KIND_IMAGE:
            filetypes = [("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tif *.tiff"), ("All files", "*.*")]
        elif kind == KIND_AUDIO:
            filetypes = [("Audio files", "*.mp3 *.wav *.m4a *.aac *.ogg *.opus *.flac"), ("All files", "*.*")]
        elif kind == KIND_VIDEO:
            filetypes = [("Video files", "*.mp4 *.webm *.avi *.mov *.mkv *.3gp"), ("All files", "*.*")]
        else:
            filetypes = [("All files", "*.*")]
        path = filedialog.askopenfilename(title=f"Select {KIND_NAMES[kind]}", filetypes=filetypes)
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as e:
            messagebox.showerror("File error", str(e))
            return
        if not data:
            messagebox.showwarning("Empty file", "Selected file is empty.")
            return
        self.start_broadcast(data, kind, os.path.basename(path))

    def start_broadcast(self, data: bytes, kind: int, filename: str):
        self.transfer_running = True
        self.stop_button.config(state="normal")
        self.progress["value"] = 0
        self.progress_label.config(text="0% | ETA --")
        t = threading.Thread(target=self.broadcast_worker, args=(data, kind, filename), daemon=True)
        t.start()

    def stop_transfer(self):
        self.transfer_running = False
        self.set_status("Stopping after current frame...", "orange")

    def broadcast_worker(self, data: bytes, kind: int, filename: str):
        tid = random.randint(1, 65535)
        chunk_size = self.get_chunk_size()
        rounds = self.get_rounds()
        gap = self.get_round_gap()
        file_crc = crc16_ccitt(data)
        name = safe_name(filename).encode("utf-8")[:80]
        total_size = len(data)
        total_chunks = (total_size + chunk_size - 1) // chunk_size
        total_frames = total_chunks * rounds
        sent_frames = 0
        sent_bytes_for_eta = 0
        total_bytes_rounds = total_size * rounds
        start = time.time()
        kind_name = KIND_NAMES.get(kind, "file")

        self.add_log(f"Carousel start: {kind_name} '{filename}', tid={tid}, size={total_size:,}, chunks={total_chunks}, chunk={chunk_size}, rounds={rounds}, file_crc=0x{file_crc:04X}")
        self.set_status(f"Broadcasting {kind_name}: {total_chunks} chunks x {rounds} rounds", "blue")

        try:
            for r in range(rounds):
                if not self.transfer_running:
                    break
                self.add_log(f"Round {r + 1}/{rounds} start")
                for seq in range(total_chunks):
                    if not self.transfer_running:
                        break
                    offset = seq * chunk_size
                    chunk = data[offset: offset + chunk_size]
                    self.send_carousel_chunk(tid, kind, seq, total_chunks, total_size, file_crc, name, chunk)
                    if not self.wait_for_tx_done(len(chunk) + len(name) + 16):
                        self.add_log("WARNING: timeout waiting for TX ESP32 frame-done marker; continuing slowly")
                    sent_frames += 1
                    sent_bytes_for_eta += len(chunk)
                    self.set_progress(sent_frames, total_frames, sent_bytes_for_eta, total_bytes_rounds, start)
                    self.set_status(f"Round {r + 1}/{rounds}, chunk {seq + 1}/{total_chunks}", "blue")
                    # Let ESP32 serial parser breathe slightly between frames.
                    time.sleep(0.01)
                if self.transfer_running and r != rounds - 1 and gap > 0:
                    self.add_log(f"Round gap {gap:.2f}s")
                    time.sleep(gap)
        except Exception as e:
            self.add_log(f"Broadcast error: {e}")
            self.set_status("Broadcast error", "red")
        finally:
            elapsed = time.time() - start
            self.transfer_running = False
            self.safe_ui(self.stop_button.config, state="disabled")
            if sent_frames >= total_frames:
                self.set_status(f"Broadcast done in {format_duration(elapsed)}", "green")
                self.add_log(f"Carousel done: sent {sent_frames}/{total_frames} frames")
            else:
                self.set_status("Broadcast stopped", "orange")
                self.add_log(f"Carousel stopped: sent {sent_frames}/{total_frames} frames")

    def send_carousel_chunk(self, tid: int, kind: int, seq: int, total_chunks: int, total_size: int, file_crc: int, name: bytes, chunk: bytes):
        # Payload format:
        # uint16 tid, uint8 kind, uint16 seq, uint16 total_chunks, uint32 total_size,
        # uint16 chunk_len, uint16 file_crc, uint8 name_len, name bytes, chunk bytes
        payload = struct.pack(">HBHHIHHB", tid, kind, seq, total_chunks, total_size, len(chunk), file_crc, len(name)) + name + chunk
        if len(payload) > 0xFFFF:
            raise ValueError("Chunk payload is too large")
        frame_crc = crc16_ccitt(payload)
        header = bytes([START_BYTE, TYPE_CAROUSEL_CHUNK, (len(payload) >> 8) & 0xFF, len(payload) & 0xFF, (frame_crc >> 8) & 0xFF, frame_crc & 0xFF])
        self.tx_done_event.clear()
        self.tx_serial.write(header + payload)
        self.tx_serial.flush()
        self.add_log(f"Sent tid={tid} chunk {seq + 1}/{total_chunks} ({len(chunk)} bytes), frame_crc=0x{frame_crc:04X}")

    def wait_for_tx_done(self, payload_len: int) -> bool:
        try:
            freq = max(1, min(50000, int(self.freq_var.get().strip())))
        except Exception:
            freq = 10000
        optical_bytes = 32 + 1 + 1 + 2 + 2 + payload_len
        ideal_seconds = optical_bytes * 10.0 / freq
        timeout = max(3.0, ideal_seconds * 3.0 + 1.0)
        return self.tx_done_event.wait(timeout=timeout)

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")

    def on_close(self):
        self.disconnect_port()
        self.destroy()


if __name__ == "__main__":
    app = LiFiTXCarouselGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
