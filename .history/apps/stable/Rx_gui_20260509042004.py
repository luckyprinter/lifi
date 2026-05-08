import os
import sys
import time
import math
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import serial
import serial.tools.list_ports

BAUDRATE = 115200

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


class TransferState:
    def __init__(self, tid, kind, total_chunks, total_size, file_crc, name):
        self.tid = tid
        self.kind = kind
        self.total_chunks = total_chunks
        self.total_size = total_size
        self.file_crc = file_crc
        self.name = name
        self.chunks = {}
        self.start_time = time.time()
        self.saved = False

    def add_chunk(self, seq, data):
        if seq in self.chunks:
            return False
        self.chunks[seq] = data
        return True

    def received_bytes(self):
        return sum(len(x) for x in self.chunks.values())

    def complete(self):
        return len(self.chunks) == self.total_chunks

    def assemble(self):
        return b"".join(self.chunks[i] for i in range(self.total_chunks))


class RXGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi RX Carousel GUI")
        self.geometry("1100x720")

        self.ser = None
        self.running = False
        self.rx_buffer = bytearray()
        self.expecting_raw = None
        self.transfers = {}
        self.last_file = None

        self.receive_folder = os.path.expanduser("~/LiFiReceived")
        os.makedirs(self.receive_folder, exist_ok=True)

        self.build_ui()
        self.refresh_ports()

    def build_ui(self):
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        tk.Label(top, text="RX Port").grid(row=0, column=0)
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, width=16)
        self.port_box.grid(row=0, column=1, padx=4)

        tk.Label(top, text="Freq Hz").grid(row=0, column=2)
        self.freq_var = tk.StringVar(value="9000")
        tk.Entry(top, textvariable=self.freq_var, width=8).grid(row=0, column=3, padx=4)

        self.debug_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="RX Debug", variable=self.debug_var, command=self.set_debug).grid(row=0, column=4)

        tk.Button(top, text="Connect", command=self.connect).grid(row=0, column=5, padx=5)
        tk.Button(top, text="Refresh", command=self.refresh_ports).grid(row=0, column=6, padx=5)
        tk.Button(top, text="Set Freq", command=self.set_freq).grid(row=0, column=7, padx=5)
        tk.Button(top, text="Reset Transfers", command=self.reset_transfers).grid(row=0, column=8, padx=5)

        folder = tk.Frame(self)
        folder.pack(fill="x", padx=10, pady=4)

        tk.Label(folder, text="Receive Folder").pack(side="left")

        self.folder_entry = tk.Entry(folder)
        self.folder_entry.insert(0, self.receive_folder)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=5)

        tk.Button(folder, text="Browse", command=self.browse_folder).pack(side="left", padx=3)
        tk.Button(folder, text="Open Folder", command=self.open_folder).pack(side="left", padx=3)
        tk.Button(folder, text="Open Last", command=self.open_last).pack(side="left", padx=3)

        self.status = tk.Label(self, text="Disconnected", fg="red")
        self.status.pack(anchor="w", padx=10)

        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.pack(fill="x", padx=10, pady=6)

        self.progress_label = tk.Label(self, text="0% | missing --")
        self.progress_label.pack(anchor="w", padx=10)

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=8)

        left = tk.Frame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right = tk.Frame(body)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        tk.Label(left, text="Received Text").pack(anchor="w")
        self.text_out = scrolledtext.ScrolledText(left, state="disabled", height=20)
        self.text_out.pack(fill="both", expand=True)

        tk.Label(right, text="RX Log").pack(anchor="w")
        self.log = scrolledtext.ScrolledText(right, state="disabled")
        self.log.pack(fill="both", expand=True)

    def log_msg(self, msg):
        def ui():
            self.log.config(state="normal")
            self.log.insert(tk.END, f"{time.strftime('%H:%M:%S')} RX: {msg}\n")
            self.log.see(tk.END)
            self.log.config(state="disabled")
        self.after(0, ui)

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
            self.port_var.set(ports[0])

    def connect(self):
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
        self.status.config(text=f"Connected: {port}", fg="green")

        threading.Thread(target=self.reader_loop, daemon=True).start()

        time.sleep(1)
        self.set_freq()
        self.set_debug()
        self.log_msg("Connected.")

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

    def set_debug(self):
        if not self.ser or not self.ser.is_open:
            return
        value = 1 if self.debug_var.get() else 0
        self.ser.write(f"DEBUG={value}\n".encode())
        self.ser.flush()
        self.log_msg(f"DEBUG={value}")

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
                needed = meta["name_len"] + meta["chunk_len"]

                if len(self.rx_buffer) < needed:
                    return

                raw = bytes(self.rx_buffer[:needed])
                del self.rx_buffer[:needed]

                if self.rx_buffer.startswith(b"\r\n"):
                    del self.rx_buffer[:2]
                elif self.rx_buffer.startswith(b"\n"):
                    del self.rx_buffer[:1]

                name_bytes = raw[:meta["name_len"]]
                chunk_data = raw[meta["name_len"]:]

                name = name_bytes.decode("utf-8", errors="replace")
                self.expecting_raw = None

                self.handle_chunk(meta, name, chunk_data)
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
                    "tid": int(parts[1]),
                    "kind": int(parts[2]),
                    "seq": int(parts[3]),
                    "total_chunks": int(parts[4]),
                    "total_size": int(parts[5]),
                    "chunk_len": int(parts[6]),
                    "file_crc": int(parts[7], 16),
                    "name_len": int(parts[8]),
                }
            except Exception as e:
                self.log_msg(f"Bad chunk line: {line} / {e}")
                self.expecting_raw = None
            return

        self.log_msg(line)

    def handle_chunk(self, meta, name, data):
        tid = meta["tid"]
        kind = meta["kind"]
        seq = meta["seq"]
        total_chunks = meta["total_chunks"]
        total_size = meta["total_size"]
        file_crc = meta["file_crc"]

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
        else:
            st = self.transfers[tid]

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

        if st.complete():
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
            os.system(f'xdg-open "{folder}"')

    def open_last(self):
        if not self.last_file or not os.path.exists(self.last_file):
            return
        if os.name == "nt":
            os.startfile(self.last_file)
        else:
            os.system(f'xdg-open "{self.last_file}"')

    def reset_transfers(self):
        self.transfers.clear()
        self.rx_buffer.clear()
        self.expecting_raw = None
        self.progress["value"] = 0
        self.progress_label.config(text="0% | missing --")
        self.log_msg("Transfers reset.")

    def on_close(self):
        self.running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = RXGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()