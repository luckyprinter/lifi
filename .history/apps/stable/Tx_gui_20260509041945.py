import os
import sys
import time
import math
import struct
import random
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
    return "".join(c if c in keep else "_" for c in name)[:80] or "file.bin"


def fmt_time(sec):
    if sec < 0 or math.isinf(sec):
        return "--"
    sec = int(sec)
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    return f"{m}m {s}s"


class TXGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi TX Carousel GUI")
        self.geometry("1100x720")

        self.ser = None
        self.running = False
        self.transfer_running = False
        self.tx_done = threading.Event()

        self.build_ui()
        self.refresh_ports()

    def build_ui(self):
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        tk.Label(top, text="TX Port").grid(row=0, column=0)
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=16)
        self.port_box.grid(row=0, column=1, padx=4)

        tk.Label(top, text="Freq Hz").grid(row=0, column=2)
        self.freq_var = tk.StringVar(value="9000")
        tk.Entry(top, textvariable=self.freq_var, width=8).grid(row=0, column=3, padx=4)

        tk.Label(top, text="Chunk").grid(row=0, column=4)
        self.chunk_var = tk.StringVar(value="512")
        ttk.Combobox(
            top,
            textvariable=self.chunk_var,
            values=["256", "512", "1024", "2048"],
            width=7,
            state="readonly",
        ).grid(row=0, column=5, padx=4)

        tk.Label(top, text="Rounds").grid(row=0, column=6)
        self.rounds_var = tk.StringVar(value="3")
        tk.Entry(top, textvariable=self.rounds_var, width=5).grid(row=0, column=7, padx=4)

        tk.Label(top, text="Round gap ms").grid(row=0, column=8)
        self.gap_var = tk.StringVar(value="500")
        tk.Entry(top, textvariable=self.gap_var, width=6).grid(row=0, column=9, padx=4)

        tk.Button(top, text="Connect", command=self.connect).grid(row=0, column=10, padx=5)
        tk.Button(top, text="Refresh", command=self.refresh_ports).grid(row=0, column=11, padx=5)
        tk.Button(top, text="Set Freq", command=self.set_freq).grid(row=0, column=12, padx=5)

        status = tk.Frame(self)
        status.pack(fill="x", padx=10)

        self.status = tk.Label(status, text="Disconnected", fg="red")
        self.status.pack(side="left")

        self.stop_btn = tk.Button(status, text="Stop", command=self.stop_transfer, state="disabled")
        self.stop_btn.pack(side="right")

        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.pack(fill="x", padx=10, pady=6)

        self.progress_label = tk.Label(self, text="0%")
        self.progress_label.pack(anchor="w", padx=10)

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=8)

        left = tk.Frame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right = tk.Frame(body)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        tk.Label(left, text="Text to Send").pack(anchor="w")
        self.text_box = scrolledtext.ScrolledText(left, height=10)
        self.text_box.pack(fill="x")

        btns = tk.Frame(left)
        btns.pack(fill="x", pady=6)

        tk.Button(btns, text="Send Text", command=self.send_text).pack(side="left", padx=3)
        tk.Button(btns, text="Send Image", command=lambda: self.send_file(KIND_IMAGE)).pack(side="left", padx=3)
        tk.Button(btns, text="Send Audio", command=lambda: self.send_file(KIND_AUDIO)).pack(side="left", padx=3)
        tk.Button(btns, text="Send Video", command=lambda: self.send_file(KIND_VIDEO)).pack(side="left", padx=3)
        tk.Button(btns, text="Send Any File", command=lambda: self.send_file(KIND_FILE)).pack(side="left", padx=3)

        tk.Label(right, text="TX Log").pack(anchor="w")
        self.log = scrolledtext.ScrolledText(right, state="disabled")
        self.log.pack(fill="both", expand=True)

    def log_msg(self, msg):
        def ui():
            self.log.config(state="normal")
            self.log.insert(tk.END, f"{time.strftime('%H:%M:%S')} TX: {msg}\n")
            self.log.see(tk.END)
            self.log.config(state="disabled")
        self.after(0, ui)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_box["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def connect(self):
        port = self.port_var.get().strip()
        if not port:
            messagebox.showwarning("Port", "Select TX COM port.")
            return

        try:
            self.ser = serial.Serial(port, BAUDRATE, timeout=0.05, write_timeout=5)
        except Exception as e:
            messagebox.showerror("Serial Error", str(e))
            return

        self.running = True
        self.status.config(text=f"Connected: {port}", fg="green")
        threading.Thread(target=self.reader_loop, daemon=True).start()

        time.sleep(1)
        self.set_freq()
        self.log_msg("Connected.")

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
            self.ser.write(f"FREQ={freq}\n".encode())
            self.ser.flush()
            self.log_msg(f"FREQ={freq}")
        except Exception as e:
            self.log_msg(f"Frequency error: {e}")

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

        self.transfer_running = True
        self.stop_btn.config(state="normal")
        threading.Thread(target=self.transfer_worker, args=(data, kind, filename), daemon=True).start()

    def transfer_worker(self, data, kind, filename):
        tid = random.randint(1, 65535)
        chunk_size = int(self.chunk_var.get())
        rounds = int(self.rounds_var.get())
        gap = int(self.gap_var.get()) / 1000.0

        file_crc = crc16_ccitt(data)
        name = safe_name(filename).encode("utf-8")
        total_size = len(data)
        total_chunks = (total_size + chunk_size - 1) // chunk_size

        total_frames = total_chunks * rounds
        sent_frames = 0

        self.log_msg(
            f"Carousel start: {KIND_NAMES[kind]} '{filename}', "
            f"tid={tid}, size={total_size}, chunks={total_chunks}, "
            f"chunk={chunk_size}, rounds={rounds}, file_crc=0x{file_crc:04X}"
        )

        start = time.time()

        for r in range(rounds):
            if not self.transfer_running:
                break

            self.log_msg(f"Round {r + 1}/{rounds} start")

            for seq in range(total_chunks):
                if not self.transfer_running:
                    break

                offset = seq * chunk_size
                chunk = data[offset:offset + chunk_size]

                payload_len = self.send_chunk(
                    tid,
                    kind,
                    seq,
                    total_chunks,
                    total_size,
                    file_crc,
                    name,
                    chunk,
                    chunk_size,
                )

                self.wait_tx_done(payload_len)

                sent_frames += 1
                pct = sent_frames * 100 / total_frames

                elapsed = time.time() - start
                rate = sent_frames / elapsed if elapsed > 0 else 0
                remain = (total_frames - sent_frames) / rate if rate > 0 else -1

                self.after(0, lambda p=pct, rm=remain: self.update_progress(p, rm))

                time.sleep(0.01)

            if r != rounds - 1 and gap > 0:
                time.sleep(gap)

        self.transfer_running = False
        self.after(0, lambda: self.stop_btn.config(state="disabled"))
        self.log_msg(f"Carousel done: sent {sent_frames}/{total_frames} frames")

    def update_progress(self, pct, remain):
        self.progress["value"] = pct
        self.progress_label.config(text=f"{pct:.1f}% | ETA {fmt_time(remain)}")

    def send_chunk(self, tid, kind, seq, total_chunks, total_size, file_crc, name, chunk, chunk_size):
        real_len = len(chunk)

        if real_len < chunk_size:
            padded_chunk = chunk + bytes(chunk_size - real_len)
        else:
            padded_chunk = chunk

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
        ) + name + padded_chunk

        frame_crc = crc16_ccitt(payload)

        header = bytes([
            START_BYTE,
            TYPE_CAROUSEL_CHUNK,
            (len(payload) >> 8) & 0xFF,
            len(payload) & 0xFF,
            (frame_crc >> 8) & 0xFF,
            frame_crc & 0xFF,
        ])

        self.tx_done.clear()
        self.ser.write(header + payload)
        self.ser.flush()

        pad_note = f", padded to {len(padded_chunk)}" if real_len != len(padded_chunk) else ""

        self.log_msg(
            f"Sent tid={tid} chunk {seq + 1}/{total_chunks} "
            f"({real_len} bytes{pad_note}), frame_crc=0x{frame_crc:04X}"
        )

        return len(payload)

    def wait_tx_done(self, payload_len):
        try:
            freq = int(self.freq_var.get())
        except Exception:
            freq = 9000

        optical_bytes = 32 + 1 + 1 + 2 + 2 + payload_len
        ideal = optical_bytes * 10 / max(1, freq)
        timeout = max(3.0, ideal * 3 + 1)

        return self.tx_done.wait(timeout=timeout)

    def on_close(self):
        self.running = False
        self.transfer_running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = TXGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()