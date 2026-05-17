import os
import subprocess
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import serial
import serial.tools.list_ports

BAUDRATE = 115200
DEFAULT_FREQUENCY_HZ = 10000


def serial_ports():
    return [f"{p.device} - {p.description}" for p in serial.tools.list_ports.comports()]


def port_device(label):
    return label.split(" - ", 1)[0].strip()


class RxGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi RX - File Transfer")
        self.geometry("940x660")
        self.minsize(820, 560)

        self.ser = None
        self.running = False
        self.buffer = bytearray()
        self.raw_mode = None
        self.last_file = None

        self.port_var = tk.StringVar()
        self.freq_var = tk.StringVar(value=str(DEFAULT_FREQUENCY_HZ))
        self.debug_var = tk.BooleanVar(value=False)
        self.receive_folder = os.path.expanduser("~/LiFiReceived")
        os.makedirs(self.receive_folder, exist_ok=True)

        self.build_ui()
        self.refresh_ports()

    def build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        ttk.Label(root, text="LiFi RX", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(root, text="For the 72a7d84 file/text receiver firmware. RX input: ESP32 GPIO5 from TEPT4400 divider.").grid(row=1, column=0, sticky="w", pady=(2, 12))

        controls = ttk.Frame(root)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="RX port").grid(row=0, column=0, sticky="w")
        self.port_box = ttk.Combobox(controls, textvariable=self.port_var, width=34)
        self.port_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8))

        ttk.Label(controls, text="Frequency Hz").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.freq_var, width=10).grid(row=1, column=2, padx=(0, 8))

        self.debug_check = ttk.Checkbutton(controls, text="RX Debug", variable=self.debug_var, command=self.set_debug)
        self.debug_check.grid(row=1, column=3, padx=(0, 8))

        self.connect_btn = ttk.Button(controls, text="Connect", command=self.toggle_connect)
        self.connect_btn.grid(row=1, column=4, padx=3)
        ttk.Button(controls, text="Refresh", command=self.refresh_ports).grid(row=1, column=5, padx=3)
        ttk.Button(controls, text="Set Freq", command=self.set_frequency).grid(row=1, column=6, padx=3)
        ttk.Button(controls, text="Open Last", command=self.open_last).grid(row=1, column=7, padx=3)

        body = ttk.PanedWindow(root, orient="horizontal")
        body.grid(row=3, column=0, sticky="nsew")

        left = ttk.Frame(body, padding=(0, 0, 8, 0))
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        body.add(left, weight=1)
        body.add(right, weight=1)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1)
        ttk.Label(left, text="Receive Folder", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        folder_bar = ttk.Frame(left)
        folder_bar.grid(row=1, column=0, sticky="ew", pady=(6, 10))
        folder_bar.columnconfigure(0, weight=1)
        self.folder_entry = ttk.Entry(folder_bar)
        self.folder_entry.insert(0, self.receive_folder)
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(folder_bar, text="Browse", command=self.browse_folder).grid(row=0, column=1)
        ttk.Button(folder_bar, text="Open Folder", command=self.open_folder).grid(row=0, column=2, padx=(6, 0))

        ttk.Label(left, text="Received Text", font=("Segoe UI", 11, "bold")).grid(row=2, column=0, sticky="w")
        self.text_out = scrolledtext.ScrolledText(left, state="disabled", font=("Segoe UI", 10))
        self.text_out.grid(row=3, column=0, sticky="nsew", pady=(6, 0))

        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        log_head = ttk.Frame(right)
        log_head.grid(row=0, column=0, sticky="ew")
        log_head.columnconfigure(0, weight=1)
        ttk.Label(log_head, text="RX Log", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
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
            messagebox.showwarning("Port", "Select the RX ESP32 serial port.")
            return
        try:
            self.ser = serial.Serial(port, BAUDRATE, timeout=0.05, write_timeout=2)
        except Exception as e:
            messagebox.showerror("Serial Error", str(e))
            return

        self.running = True
        threading.Thread(target=self.reader_loop, daemon=True).start()
        time.sleep(1.0)
        self.set_frequency()
        self.set_debug()
        self.connect_btn.config(text="Disconnect")
        self.log_msg(f"Connected to {port}")

    def disconnect(self):
        self.running = False
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.ser = None
            self.connect_btn.config(text="Connect")
            self.log_msg("Disconnected")

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

    def set_debug(self):
        if not self.ser or not self.ser.is_open:
            return
        value = 1 if self.debug_var.get() else 0
        try:
            self.ser.write(f"DEBUG={value}\n".encode("ascii"))
            self.ser.flush()
            self.log_msg(f"DEBUG={value}")
        except Exception as e:
            self.log_msg(f"Debug error: {e}")

    def reader_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                data = self.ser.read(4096)
            except Exception as e:
                self.log_msg(f"Read error: {e}")
                break
            if data:
                self.buffer.extend(data)
                self.process_buffer()

    def process_buffer(self):
        while True:
            if self.raw_mode is not None:
                mode = self.raw_mode
                needed = mode["size"] - len(mode["data"])
                if needed > 0:
                    if not self.buffer:
                        return
                    take = min(needed, len(self.buffer))
                    mode["data"].extend(self.buffer[:take])
                    del self.buffer[:take]
                    if len(mode["data"]) < mode["size"]:
                        return

                self.finish_raw_payload()
                continue

            newline = self.buffer.find(b"\n")
            if newline < 0:
                return
            line = bytes(self.buffer[:newline + 1])
            del self.buffer[:newline + 1]
            self.handle_line(line.decode("utf-8", errors="replace").strip())

    def handle_line(self, line):
        if not line:
            return
        if line.startswith("RX_TEXT_START:"):
            size = int(line.split(":", 1)[1])
            self.raw_mode = {"kind": "text", "size": size, "data": bytearray()}
            self.log_msg(f"Text payload start: {size} bytes")
            return
        if line.startswith("RX_FILE_START:"):
            size = int(line.split(":", 1)[1])
            self.raw_mode = {"kind": "file", "size": size, "data": bytearray()}
            self.log_msg(f"File payload start: {size} bytes")
            return
        if line.startswith("RX_TEXT_CRC_OK"):
            self.log_msg("Text CRC OK")
            return
        if line.startswith("RX_FILE_CRC_OK"):
            self.log_msg("File CRC OK")
            return
        if line.startswith("RX_TEXT_CRC_FAIL") or line.startswith("RX_FILE_CRC_FAIL"):
            self.log_msg(line)
            return
        if line.startswith("RX_TEXT_COMPLETE") or line.startswith("RX_FILE_COMPLETE"):
            self.log_msg(line)
            return
        if line.startswith(("RX ", "RX_", "ESP32", "FREQ", "DEBUG")):
            self.log_msg(line)

    def finish_raw_payload(self):
        mode = self.raw_mode
        self.raw_mode = None
        data = bytes(mode["data"])

        if self.buffer.startswith(b"\r\n"):
            del self.buffer[:2]
        elif self.buffer.startswith(b"\n"):
            del self.buffer[:1]

        if mode["kind"] == "text":
            text = data.decode("utf-8", errors="replace")
            self.text_out.configure(state="normal")
            self.text_out.insert("end", text)
            if not text.endswith("\n"):
                self.text_out.insert("end", "\n")
            self.text_out.see("end")
            self.text_out.configure(state="disabled")
            self.log_msg(f"Received text: {len(data)} bytes")
            return

        folder = self.folder_entry.get().strip() or self.receive_folder
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"received_{int(time.time())}.bin")
        with open(path, "wb") as f:
            f.write(data)
        self.last_file = path
        self.log_msg(f"Saved file: {path}")

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_entry.get().strip() or self.receive_folder)
        if folder:
            self.folder_entry.delete(0, "end")
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
    app = RxGui()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
