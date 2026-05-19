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
    cleaned = "".join(ch if ch in keep else "_" for ch in name)
    return cleaned.strip(" ._") or "received_file.bin"


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


class TransferState:
    def __init__(self, tid: int, kind: int, total_chunks: int, total_size: int, file_crc: int, name: str):
        self.tid = tid
        self.kind = kind
        self.total_chunks = total_chunks
        self.total_size = total_size
        self.file_crc = file_crc
        self.name = name
        self.chunks = {}
        self.start_time = time.time()
        self.saved = False

    def add_chunk(self, seq: int, data: bytes) -> bool:
        if seq in self.chunks:
            return False
        self.chunks[seq] = data
        return True

    def received_bytes(self) -> int:
        return sum(len(x) for x in self.chunks.values())

    def complete(self) -> bool:
        return len(self.chunks) == self.total_chunks

    def assemble(self) -> bytes:
        return b"".join(self.chunks[i] for i in range(self.total_chunks))


class LiFiRXCarouselGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi RX - One-Way Carousel Receiver")
        self.geometry("1080x720")

        self.rx_serial = None
        self.reader_thread = None
        self.running = False
        self.rx_buffer = bytearray()
        self.expecting_raw = None  # metadata dict from RX_CAROUSEL_CHUNK line
        self.transfers = {}
        self.active_tid = None
        self.last_received_file = None
        self.receive_folder = os.path.expanduser("~/LiFiReceived")
        os.makedirs(self.receive_folder, exist_ok=True)

        self.create_widgets()
        self.populate_ports()

    def create_widgets(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=8)

        tk.Label(toolbar, text="RX Port:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(toolbar, width=18, textvariable=self.port_var)
        self.port_combo.grid(row=0, column=1, padx=4)

        tk.Label(toolbar, text="Freq Hz:").grid(row=0, column=2, sticky="e")
        self.freq_var = tk.StringVar(value="10000")
        self.freq_entry = tk.Entry(toolbar, width=9, textvariable=self.freq_var)
        self.freq_entry.grid(row=0, column=3, padx=4)
        self.freq_entry.bind("<Return>", lambda _e: self.apply_frequency())
        tk.Button(toolbar, text="Set Freq", command=self.apply_frequency).grid(row=0, column=4, padx=4)

        self.debug_var = tk.BooleanVar(value=False)
        tk.Checkbutton(toolbar, text="RX Debug", variable=self.debug_var, command=self.update_debug).grid(row=0, column=5, padx=4)

        self.connect_button = tk.Button(toolbar, text="Connect", command=self.connect_port)
        self.connect_button.grid(row=0, column=6, padx=8)
        tk.Button(toolbar, text="Refresh", command=self.refresh_ports).grid(row=0, column=7, padx=4)
        tk.Button(toolbar, text="Reset Transfers", command=self.reset_transfers).grid(row=0, column=8, padx=4)

        folder = tk.Frame(self)
        folder.pack(fill="x", padx=10, pady=3)
        tk.Label(folder, text="Receive folder:").pack(side="left")
        self.folder_entry = tk.Entry(folder, width=78)
        self.folder_entry.insert(0, self.receive_folder)
        self.folder_entry.pack(side="left", padx=4)
        tk.Button(folder, text="Browse", command=self.choose_receive_folder).pack(side="left", padx=3)
        tk.Button(folder, text="Open Folder", command=self.open_receive_folder).pack(side="left", padx=3)
        tk.Button(folder, text="Open Last Received", command=self.open_last_received).pack(side="left", padx=3)

        status = tk.Frame(self)
        status.pack(fill="x", padx=10, pady=4)
        self.rx_status = tk.Label(status, text="RX: Disconnected", fg="red")
        self.rx_status.pack(side="left")
        self.transfer_status = tk.Label(status, text="Idle", fg="blue")
        self.transfer_status.pack(side="left", padx=20)

        progress_frame = tk.Frame(self)
        progress_frame.pack(fill="x", padx=10, pady=4)
        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.progress_label = tk.Label(progress_frame, text="0% | missing -- | ETA --", width=36)
        self.progress_label.pack(side="right")

        content = tk.Frame(self)
        content.pack(fill="both", expand=True, padx=10, pady=8)
        left = tk.Frame(content)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = tk.Frame(content)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        top_left = tk.Frame(left)
        top_left.pack(fill="x")
        tk.Label(top_left, text="Received Text / Completed Transfer", font=("Arial", 12, "bold")).pack(side="left")
        tk.Button(top_left, text="Clear Text", command=self.clear_text).pack(side="right")
        self.text_output = scrolledtext.ScrolledText(left, state="disabled", height=16, bg="#f8fff8")
        self.text_output.pack(fill="both", expand=True, pady=4)

        top_right = tk.Frame(right)
        top_right.pack(fill="x")
        tk.Label(top_right, text="RX Log", font=("Arial", 12, "bold")).pack(side="left")
        tk.Button(top_right, text="Clear Log", command=self.clear_log).pack(side="right")
        self.log = scrolledtext.ScrolledText(right, state="disabled", height=34, bg="#eef7ff")
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
        self.log.insert(tk.END, f"{time.strftime('%H:%M:%S')} RX: {message}\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def add_text_output(self, text: str):
        def apply():
            self.text_output.configure(state="normal")
            self.text_output.insert(tk.END, text + "\n")
            self.text_output.see(tk.END)
            self.text_output.configure(state="disabled")
        self.safe_ui(apply)

    def set_status(self, text: str, color="blue"):
        self.safe_ui(self.transfer_status.config, text=text, fg=color)

    def update_progress(self, st: TransferState):
        total = max(1, st.total_size)
        done = min(st.total_size, st.received_bytes())
        pct = min(100.0, done * 100.0 / total)
        missing = st.total_chunks - len(st.chunks)
        elapsed = max(0.001, time.time() - st.start_time)
        rate = done / elapsed if done > 0 else 0
        eta = (st.total_size - done) / rate if rate > 0 else -1
        def apply():
            self.progress["value"] = pct
            self.progress_label.config(text=f"{pct:5.1f}% | missing {missing} | ETA {format_duration(eta)}")
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
            messagebox.showwarning("Missing port", "Select RX serial port.")
            return
        try:
            self.rx_serial = serial.Serial(port, BAUDRATE, timeout=0.05, write_timeout=5)
        except Exception as e:
            messagebox.showerror("Connection failed", str(e))
            return
        self.running = True
        self.rx_status.config(text=f"RX: {port}", fg="green")
        self.connect_button.config(text="Disconnect", command=self.disconnect_port)
        self.set_status("Waiting for ESP32 boot/reset...", "orange")
        def boot():
            time.sleep(2.3)
            try:
                self.rx_serial.reset_input_buffer()
            except Exception:
                pass
            self.reader_thread = threading.Thread(target=self.reader_loop, daemon=True)
            self.reader_thread.start()
            self.apply_frequency()
            self.update_debug()
            self.set_status("Connected. Waiting for optical chunks...", "green")
            self.add_log("Connected. One-way carousel RX ready.")
        threading.Thread(target=boot, daemon=True).start()

    def disconnect_port(self):
        self.running = False
        try:
            if self.rx_serial and self.rx_serial.is_open:
                self.rx_serial.close()
        except Exception:
            pass
        self.rx_status.config(text="RX: Disconnected", fg="red")
        self.connect_button.config(text="Connect", command=self.connect_port)
        self.set_status("Idle", "blue")
        self.add_log("Disconnected.")

    def apply_frequency(self):
        try:
            freq = int(self.freq_var.get().strip())
        except ValueError:
            messagebox.showwarning("Invalid frequency", "Enter 1 to 50000 Hz.")
            return
        if not 1 <= freq <= 50000:
            messagebox.showwarning("Invalid frequency", "Frequency must be 1 to 50000 Hz.")
            return
        if self.rx_serial and self.rx_serial.is_open:
            try:
                self.rx_serial.write(f"FREQ={freq}\n".encode("ascii"))
                self.rx_serial.flush()
                self.add_log(f"Sent RX frequency command: FREQ={freq}")
            except Exception as e:
                self.add_log(f"Failed to set frequency: {e}")

    def update_debug(self):
        if self.rx_serial and self.rx_serial.is_open:
            try:
                value = 1 if self.debug_var.get() else 0
                self.rx_serial.write(f"DEBUG={value}\n".encode("ascii"))
                self.rx_serial.flush()
                self.add_log(f"Sent RX debug command: DEBUG={value}")
            except Exception as e:
                self.add_log(f"Failed to set debug: {e}")

    def reader_loop(self):
        while self.running and self.rx_serial and self.rx_serial.is_open:
            try:
                chunk = self.rx_serial.read(4096)
            except Exception as e:
                self.add_log(f"Serial read error: {e}")
                break
            if chunk:
                self.rx_buffer.extend(chunk)
                self.process_buffer()
        self.add_log("RX serial monitor stopped.")

    def process_buffer(self):
        while True:
            if self.expecting_raw is not None:
                meta = self.expecting_raw
                needed = meta["name_len"] + meta["chunk_len"]
                if len(self.rx_buffer) < needed:
                    return
                raw = bytes(self.rx_buffer[:needed])
                del self.rx_buffer[:needed]
                # Consume one optional newline from Serial.println() after raw bytes.
                if self.rx_buffer.startswith(b"\r\n"):
                    del self.rx_buffer[:2]
                elif self.rx_buffer.startswith(b"\n"):
                    del self.rx_buffer[:1]
                name_bytes = raw[:meta["name_len"]]
                data = raw[meta["name_len"]:]
                name = name_bytes.decode("utf-8", errors="replace") or "received_file.bin"
                self.expecting_raw = None
                self.handle_chunk(meta, name, data)
                continue

            idx = self.rx_buffer.find(b"\n")
            if idx < 0:
                return
            line_bytes = bytes(self.rx_buffer[:idx + 1])
            del self.rx_buffer[:idx + 1]
            line = line_bytes.rstrip(b"\r\n").decode("utf-8", errors="replace")
            self.handle_line(line)

    def handle_line(self, line: str):
        if not line:
            return
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
            except Exception:
                self.add_log(f"Malformed chunk line: {line}")
                self.expecting_raw = None
            return
        if line.startswith("RX_CAROUSEL_BAD_CRC") or line.startswith("RX_CAROUSEL_BAD_HEADER"):
            self.add_log(line)
            return
        self.add_log(line)

    def handle_chunk(self, meta: dict, name: str, data: bytes):
        tid = meta["tid"]
        kind = meta["kind"]
        seq = meta["seq"]
        total_chunks = meta["total_chunks"]
        total_size = meta["total_size"]
        file_crc = meta["file_crc"]

        if tid not in self.transfers:
            st = TransferState(tid, kind, total_chunks, total_size, file_crc, safe_filename(name))
            self.transfers[tid] = st
            self.active_tid = tid
            self.add_log(f"New transfer tid={tid}: {KIND_NAMES.get(kind, 'file')} '{st.name}', {total_size:,} bytes, {total_chunks} chunks, file_crc=0x{file_crc:04X}")
        else:
            st = self.transfers[tid]

        if st.saved:
            return
        if seq >= st.total_chunks:
            self.add_log(f"Ignored invalid seq {seq} for tid={tid}")
            return

        added = st.add_chunk(seq, data)
        if added:
            self.add_log(f"Stored tid={tid} chunk {seq + 1}/{st.total_chunks} ({len(data)} bytes). Missing {st.total_chunks - len(st.chunks)}")
        else:
            # Duplicate chunks are expected in carousel mode.
            self.add_log(f"Duplicate tid={tid} chunk {seq + 1}/{st.total_chunks} ignored")

        self.update_progress(st)
        self.set_status(f"Receiving tid={tid}: {len(st.chunks)}/{st.total_chunks} chunks", "blue")

        if st.complete():
            self.finish_transfer(st)

    def finish_transfer(self, st: TransferState):
        try:
            data = st.assemble()
        except Exception as e:
            self.add_log(f"Assembly failed for tid={st.tid}: {e}")
            return
        actual_crc = crc16_ccitt(data)
        if len(data) != st.total_size or actual_crc != st.file_crc:
            self.add_log(f"RX_FILE_REBUILD_FAIL tid={st.tid}: len={len(data)}/{st.total_size}, crc=0x{actual_crc:04X} expected=0x{st.file_crc:04X}")
            self.set_status("Rebuild failed", "red")
            return

        st.saved = True
        elapsed = time.time() - st.start_time
        if st.kind == KIND_TEXT:
            text = data.decode("utf-8", errors="replace")
            self.add_text_output(f"--- Received text tid={st.tid}, {len(data)} bytes, {format_duration(elapsed)} ---")
            self.add_text_output(text.rstrip("\n"))
            self.add_log(f"RX_TEXT_CAROUSEL_OK tid={st.tid}: {len(data)} bytes, crc=0x{actual_crc:04X}")
            self.set_status(f"Text complete in {format_duration(elapsed)}", "green")
            return

        folder = self.folder_entry.get().strip() or self.receive_folder
        os.makedirs(folder, exist_ok=True)
        name = st.name
        root, ext = os.path.splitext(name)
        if not ext:
            ext = DEFAULT_EXT.get(st.kind, ".bin")
            name = root + ext
        path = os.path.join(folder, f"received_{int(time.time())}_{safe_filename(name)}")
        try:
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            self.add_log(f"Save failed: {e}")
            self.set_status("Save failed", "red")
            return
        self.last_received_file = path
        self.add_log(f"Saved file: {path}")
        self.add_log(f"RX_FILE_CAROUSEL_OK tid={st.tid}: {len(data)} bytes, crc=0x{actual_crc:04X}")
        self.set_status(f"File complete in {format_duration(elapsed)}", "green")

    def reset_transfers(self):
        self.transfers.clear()
        self.active_tid = None
        self.expecting_raw = None
        self.rx_buffer.clear()
        self.progress["value"] = 0
        self.progress_label.config(text="0% | missing -- | ETA --")
        self.set_status("Transfers reset", "orange")
        self.add_log("All transfer states cleared.")

    def choose_receive_folder(self):
        folder = filedialog.askdirectory(initialdir=self.receive_folder)
        if folder:
            self.receive_folder = folder
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder)

    def open_receive_folder(self):
        folder = self.folder_entry.get().strip() or self.receive_folder
        if not os.path.isdir(folder):
            messagebox.showwarning("Folder missing", "Receive folder does not exist.")
            return
        try:
            if os.name == "nt":
                os.startfile(folder)
            elif sys.platform == "darwin":
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}"')
        except Exception as e:
            messagebox.showerror("Open folder", str(e))

    def open_last_received(self):
        if not self.last_received_file or not os.path.exists(self.last_received_file):
            messagebox.showinfo("Open Last Received", "No received file yet.")
            return
        try:
            if os.name == "nt":
                os.startfile(self.last_received_file)
            elif sys.platform == "darwin":
                os.system(f'open "{self.last_received_file}"')
            else:
                os.system(f'xdg-open "{self.last_received_file}"')
        except Exception as e:
            messagebox.showerror("Open file", str(e))

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")

    def clear_text(self):
        self.text_output.configure(state="normal")
        self.text_output.delete("1.0", tk.END)
        self.text_output.configure(state="disabled")

    def on_close(self):
        self.disconnect_port()
        self.destroy()


if __name__ == "__main__":
    app = LiFiRXCarouselGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()