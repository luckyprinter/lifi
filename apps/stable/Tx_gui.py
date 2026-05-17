import os
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import serial
import serial.tools.list_ports

BAUDRATE = 115200
START_BYTE = 0x02
TYPE_FILE_CRC = 0x01
TYPE_TEXT_CRC = 0x02
DEFAULT_FREQUENCY_HZ = 10000
MAX_PAYLOAD_SIZE = 65535


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def serial_ports():
    ports = []
    for p in serial.tools.list_ports.comports():
        label = f"{p.device} - {p.description}"
        ports.append(label)
    return ports


def port_device(label):
    return label.split(" - ", 1)[0].strip()


def fmt_bytes(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


class TxGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi TX - File Transfer")
        self.geometry("940x660")
        self.minsize(820, 560)

        self.ser = None
        self.reader_running = False
        self.sending = False

        self.port_var = tk.StringVar()
        self.freq_var = tk.StringVar(value=str(DEFAULT_FREQUENCY_HZ))
        self.chunk_var = tk.StringVar(value="64")

        self.build_ui()
        self.refresh_ports()

    def build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        title = ttk.Label(root, text="LiFi TX", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")
        subtitle = ttk.Label(
            root,
            text="For the 72a7d84 file/text firmware. Current TX hardware: ESP32 GPIO5 -> 220R -> IRLZ44N gate.",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 12))

        controls = ttk.Frame(root)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="TX port").grid(row=0, column=0, sticky="w")
        self.port_box = ttk.Combobox(controls, textvariable=self.port_var, width=34)
        self.port_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8))

        ttk.Label(controls, text="Frequency Hz").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.freq_var, width=10).grid(row=1, column=2, padx=(0, 8))

        ttk.Label(controls, text="USB chunk").grid(row=0, column=3, sticky="w")
        ttk.Combobox(controls, textvariable=self.chunk_var, values=["32", "64", "128", "256"], width=8, state="readonly").grid(row=1, column=3, padx=(0, 8))

        self.connect_btn = ttk.Button(controls, text="Connect", command=self.toggle_connect)
        self.connect_btn.grid(row=1, column=4, padx=3)
        ttk.Button(controls, text="Refresh", command=self.refresh_ports).grid(row=1, column=5, padx=3)
        ttk.Button(controls, text="Set Freq", command=self.set_frequency).grid(row=1, column=6, padx=3)

        body = ttk.PanedWindow(root, orient="horizontal")
        body.grid(row=3, column=0, sticky="nsew")

        left = ttk.Frame(body, padding=(0, 0, 8, 0))
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        body.add(left, weight=1)
        body.add(right, weight=1)

        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="Text Payload", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.text_box = scrolledtext.ScrolledText(left, height=10, font=("Segoe UI", 10))
        self.text_box.grid(row=1, column=0, sticky="nsew", pady=(6, 8))

        send_bar = ttk.Frame(left)
        send_bar.grid(row=2, column=0, sticky="ew")
        ttk.Button(send_bar, text="Send Text", command=self.send_text).pack(side="left", padx=(0, 5))
        ttk.Button(send_bar, text="Send File", command=self.send_file).pack(side="left", padx=5)

        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        log_head = ttk.Frame(right)
        log_head.grid(row=0, column=0, sticky="ew")
        log_head.columnconfigure(0, weight=1)
        ttk.Label(log_head, text="TX Log", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(log_head, text="Clear", command=self.clear_log).grid(row=0, column=1, sticky="e")

        self.log = scrolledtext.ScrolledText(right, state="disabled", font=("Consolas", 9))
        self.log.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

    def refresh_ports(self):
        ports = serial_ports()
        self.port_box["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def toggle_connect(self):
        if self.ser and self.ser.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        port = port_device(self.port_var.get())
        if not port:
            messagebox.showwarning("Port", "Select the TX ESP32 serial port.")
            return
        try:
            self.ser = serial.Serial(port, BAUDRATE, timeout=0.1, write_timeout=5)
        except Exception as e:
            messagebox.showerror("Serial Error", str(e))
            return

        self.reader_running = True
        threading.Thread(target=self.reader_loop, daemon=True).start()
        time.sleep(1.0)
        self.set_frequency()
        self.connect_btn.config(text="Disconnect")
        self.log_msg(f"Connected to {port}")

    def disconnect(self):
        self.reader_running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.ser = None
            self.connect_btn.config(text="Connect")
            self.log_msg("Disconnected")

    def reader_loop(self):
        while self.reader_running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline()
            except Exception:
                break
            if line:
                self.log_msg(line.decode("utf-8", errors="replace").strip())

    def set_frequency(self):
        if not self.ser or not self.ser.is_open:
            return
        try:
            freq = int(self.freq_var.get())
            if freq <= 0:
                raise ValueError("Frequency must be positive")
            self.ser.write(f"FREQ={freq}\n".encode("ascii"))
            self.ser.flush()
            self.log_msg(f"FREQ={freq}")
        except Exception as e:
            self.log_msg(f"Frequency error: {e}")

    def send_text(self):
        text = self.text_box.get("1.0", "end-1c")
        if not text:
            return
        if not text.endswith("\n"):
            text += "\n"
        self.start_send(text.encode("utf-8"), TYPE_TEXT_CRC, "text")

    def send_file(self):
        path = filedialog.askopenfilename(title="Select file to send")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as e:
            messagebox.showerror("File Error", str(e))
            return
        self.start_send(data, TYPE_FILE_CRC, os.path.basename(path))

    def start_send(self, data, frame_type, name):
        if self.sending:
            messagebox.showwarning("Busy", "A send is already running.")
            return
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("Serial", "Connect TX first.")
            return
        if len(data) > MAX_PAYLOAD_SIZE:
            messagebox.showerror("Too Large", "This older firmware supports up to 65535 bytes per frame.")
            return

        self.sending = True
        threading.Thread(target=self.send_worker, args=(data, frame_type, name), daemon=True).start()

    def send_worker(self, data, frame_type, name):
        try:
            chunk_size = int(self.chunk_var.get())
            crc = crc16_ccitt(data)
            size = len(data)
            header = bytes([
                START_BYTE,
                frame_type,
                (size >> 8) & 0xFF,
                size & 0xFF,
                (crc >> 8) & 0xFF,
                crc & 0xFF,
            ])

            start = time.time()
            self.ser.write(header)
            self.ser.flush()
            sent = 0

            for offset in range(0, size, chunk_size):
                chunk = data[offset:offset + chunk_size]
                self.ser.write(chunk)
                self.ser.flush()
                sent += len(chunk)
                self.log_msg(f"USB sent {sent}/{size} bytes")
                time.sleep(0.01)

            elapsed = time.time() - start
            self.log_msg(f"Frame sent: {name}, {fmt_bytes(size)}, type=0x{frame_type:02X}, crc=0x{crc:04X}, usb_time={elapsed:.2f}s")
        except Exception as e:
            self.log_msg(f"Send error: {e}")
        finally:
            self.sending = False

    def log_msg(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", f"{time.strftime('%H:%M:%S')}  {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def on_close(self):
        self.disconnect()
        self.destroy()


if __name__ == "__main__":
    app = TxGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
