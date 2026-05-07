import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import ctypes

import serial
import serial.tools.list_ports

BAUDRATE = 115200
HEADER_START = 0x02
MAX_FREQUENCY_HZ = 50000
TEXT_FRAME_MAX = 0xFFFF  # Text is now sent as one complete CRC frame


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def safe_str(data):
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return str(data)


class FileTransferGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiFi File Transfer - 50 kHz Experimental")
        self.geometry("1100x700")

        self.tx_serial = None
        self.rx_serial = None
        self.rx_thread = None
        self.rx_running = False

        self.receive_folder = os.path.expanduser("~/LiFiReceived")
        os.makedirs(self.receive_folder, exist_ok=True)

        self.expecting_file = False
        self.expected_file_size = 0
        self.received_file_bytes = bytearray()
        self.expecting_text = False
        self.expected_text_size = 0
        self.received_text_bytes = bytearray()
        self.receive_buffer = bytearray()
        self.receive_file_extension = ".bin"
        self.last_received_file = None
        self.pending_file_name = None
        self.crc_enabled = tk.BooleanVar(value=True)
        self.debug_enabled = tk.BooleanVar(value=False)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_label_var = tk.StringVar(value="Progress: idle")
        self.transfer_start_time = None
        self.transfer_total_bytes = 0
        self.transfer_done_bytes = 0

        self.create_widgets()

    def create_widgets(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=8)

        tk.Label(toolbar, text="TX Port:").grid(row=0, column=0, sticky="w")
        self.tx_port_var = tk.StringVar()
        self.tx_port_combo = ttk.Combobox(toolbar, width=20, textvariable=self.tx_port_var)
        if os.name == 'nt':  # Windows
            tx_default = "COM1"
        else:  # Linux/Mac
            tx_default = "/dev/ttyUSB0"
        self.tx_port_var.set(tx_default)
        self.tx_port_combo.grid(row=0, column=1, padx=4)

        tk.Label(toolbar, text="RX Port:").grid(row=0, column=2, sticky="w")
        self.rx_port_var = tk.StringVar()
        self.rx_port_combo = ttk.Combobox(toolbar, width=20, textvariable=self.rx_port_var)
        if os.name == 'nt':  # Windows
            rx_default = "COM2"
        else:  # Linux/Mac
            rx_default = "/dev/ttyUSB1"
        self.rx_port_var.set(rx_default)
        self.rx_port_combo.grid(row=0, column=3, padx=4)

        tk.Label(toolbar, text="Frequency:").grid(row=0, column=4, sticky="w")
        self.freq_entry = tk.Entry(toolbar, width=10)
        self.freq_entry.insert(0, "500")
        self.freq_entry.grid(row=0, column=5, padx=4)
        self.freq_entry.bind("<Return>", lambda event: self.apply_frequency())

        self.set_freq_button = tk.Button(toolbar, text="Set Freq", command=self.apply_frequency)
        self.set_freq_button.grid(row=0, column=6, padx=4)

        self.connect_button = tk.Button(toolbar, text="Connect", command=self.connect_ports)
        self.connect_button.grid(row=0, column=7, padx=8)

        self.refresh_ports_button = tk.Button(toolbar, text="Refresh Ports", command=self.refresh_serial_ports)
        self.refresh_ports_button.grid(row=0, column=8, padx=4)

        self.list_ports_button = tk.Button(toolbar, text="Show Ports", command=self.list_available_ports)
        self.list_ports_button.grid(row=0, column=9, padx=4)

        self.debug_check = tk.Checkbutton(toolbar, text="RX Debug", variable=self.debug_enabled, command=self.update_rx_debug)
        self.debug_check.grid(row=0, column=10, padx=4)

        self.crc_check = tk.Checkbutton(toolbar, text="CRC Check", variable=self.crc_enabled)
        self.crc_check.grid(row=0, column=11, padx=4)

        self.populate_serial_ports()

        folder_frame = tk.Frame(self)
        folder_frame.pack(fill="x", padx=10, pady=4)

        tk.Label(folder_frame, text="Receive Folder:").pack(side="left")
        self.receive_folder_entry = tk.Entry(folder_frame, width=60)
        self.receive_folder_entry.insert(0, self.receive_folder)
        self.receive_folder_entry.pack(side="left", padx=4)
        tk.Button(folder_frame, text="Browse", command=self.choose_receive_folder).pack(side="left", padx=4)

        status_frame = tk.Frame(self)
        status_frame.pack(fill="x", padx=10, pady=4)
        self.tx_status = tk.Label(status_frame, text="TX: Disconnected", fg="red")
        self.tx_status.pack(side="left", padx=4)
        self.rx_status = tk.Label(status_frame, text="RX: Disconnected", fg="red")
        self.rx_status.pack(side="left", padx=24)
        self.admin_status = tk.Label(
            status_frame,
            text=f"Admin: {'Yes' if self.is_windows_admin() else 'No'}",
            fg="green" if self.is_windows_admin() else "orange",
        )
        self.admin_status.pack(side="left", padx=24)
        self.transfer_status = tk.Label(status_frame, text="Idle", fg="blue")
        self.transfer_status.pack(side="left", padx=24)

        progress_frame = tk.Frame(self)
        progress_frame.pack(fill="x", padx=10, pady=4)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.progress_label = tk.Label(progress_frame, textvariable=self.progress_label_var, width=42, anchor="w")
        self.progress_label.pack(side="left")

        content = tk.Frame(self)
        content.pack(fill="both", expand=True, padx=10, pady=8)

        left = tk.Frame(content)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(content)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(left, text="Send Text / Raw Bytes", font=("Arial", 12, "bold")).pack(anchor="w")
        self.send_text_box = scrolledtext.ScrolledText(left, height=6)
        self.send_text_box.pack(fill="x", pady=4)

        send_buttons = tk.Frame(left)
        send_buttons.pack(fill="x", pady=4)
        tk.Button(send_buttons, text="Send Text", command=self.send_text).pack(side="left", padx=4)
        tk.Button(send_buttons, text="Send Image/File", command=self.send_file).pack(side="left", padx=4)
        tk.Button(send_buttons, text="Clear TX Log", command=self.clear_tx_log).pack(side="right", padx=4)

        self.tx_log = scrolledtext.ScrolledText(left, state="disabled", height=18, bg="#f7f7f7")
        self.tx_log.pack(fill="both", expand=True, pady=4)

        tk.Label(right, text="Receive / RX Debug", font=("Arial", 12, "bold")).pack(anchor="w")
        log_buttons = tk.Frame(right)
        log_buttons.pack(fill="x", pady=4)
        tk.Button(log_buttons, text="Clear RX Log", command=self.clear_rx_log).pack(side="left", padx=4)
        tk.Button(log_buttons, text="Open Received Folder", command=self.open_receive_folder).pack(side="right", padx=4)

        self.rx_log = scrolledtext.ScrolledText(right, state="disabled", height=34, bg="#eef7ff")
        self.rx_log.pack(fill="both", expand=True, pady=4)

    def choose_receive_folder(self):
        folder = filedialog.askdirectory(initialdir=self.receive_folder)
        if folder:
            self.receive_folder = folder
            self.receive_folder_entry.delete(0, tk.END)
            self.receive_folder_entry.insert(0, self.receive_folder)

    def connect_ports(self):
        tx_port_name = self.tx_port_var.get().strip()
        rx_port_name = self.rx_port_var.get().strip()
        freq = self.freq_entry.get().strip()

        if os.name == 'nt' and not self.is_windows_admin():
            should_restart = messagebox.askyesno(
                "Administrator required",
                "This app is not running as administrator. Some COM ports may fail with Access Denied.\n\nRelaunch as administrator now?",
            )
            if should_restart:
                if self.relaunch_as_admin():
                    self.destroy()
                    sys.exit(0)
                return

        if not tx_port_name or not rx_port_name:
            messagebox.showwarning("Missing Ports", "Please enter both TX and RX serial port names.")
            return

        try:
            # ESP32 boards often auto-reset when a PC opens the COM port.
            # Open the ports, force DTR/RTS inactive, then wait before sending FREQ/DEBUG.
            self.tx_serial = serial.Serial(
                tx_port_name, BAUDRATE, timeout=1, write_timeout=3,
                rtscts=False, dsrdtr=False
            )
            self.rx_serial = serial.Serial(
                rx_port_name, BAUDRATE, timeout=0.1, write_timeout=3,
                rtscts=False, dsrdtr=False
            )
            try:
                self.tx_serial.setDTR(False)
                self.tx_serial.setRTS(False)
                self.rx_serial.setDTR(False)
                self.rx_serial.setRTS(False)
            except Exception:
                pass
        except serial.SerialException as e:
            error_msg = str(e)
            if "Access is denied" in error_msg or "PermissionError" in error_msg:
                error_msg += "\n\nOn Windows, try running the application as Administrator.\nAlso ensure no other programs are using the COM ports."
            elif "could not open port" in error_msg:
                error_msg += "\n\nCheck that the COM port exists in Device Manager and is not in use by another application."
            messagebox.showerror("Connection Failed", error_msg)
            return
        except Exception as e:
            messagebox.showerror("Connection Failed", f"Unexpected error: {str(e)}")
            return

        self.connect_button.config(text="Disconnect", command=self.disconnect_ports)
        self.tx_status.config(text=f"TX: {tx_port_name}", fg="green")
        self.rx_status.config(text=f"RX: {rx_port_name}", fg="green")
        self.transfer_status.config(text="ESP32 reset wait...", fg="orange")
        self.add_tx_log("Ports opened. Waiting for ESP32 auto-reset/boot before sending FREQ...")
        self.update_idletasks()

        # Opening a CP210x/CH340 ESP32 serial port can reset the ESP32.
        # If FREQ is sent immediately, the RX may miss it and stay at 500 Hz.
        time.sleep(2.3)

        # Drop boot text already printed before the GUI starts monitoring.
        # New FREQ/DEBUG confirmations will still be shown after the RX thread starts.
        try:
            self.tx_serial.reset_input_buffer()
            self.rx_serial.reset_input_buffer()
        except Exception:
            pass

        if freq.isdigit():
            self.set_frequency(int(freq))
            time.sleep(0.15)

        self.update_rx_debug()
        time.sleep(0.05)

        self.rx_running = True
        self.rx_thread = threading.Thread(target=self.rx_loop, daemon=True)
        self.rx_thread.start()
        self.transfer_status.config(text="Connected", fg="green")
        self.add_tx_log("Connected to TX and RX ports.")
        self.add_rx_log("Waiting for RX data...")

    def is_windows_admin(self):
        if os.name != "nt":
            return True
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def relaunch_as_admin(self):
        if os.name != "nt":
            return False

        executable = sys.executable
        script = os.path.abspath(sys.argv[0])
        params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
        cmd = f'"{script}" {params}'.strip()

        try:
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, cmd, None, 1)
            if result <= 32:
                raise RuntimeError(f"ShellExecuteW failed with return code {result}")
            return True
        except Exception as e:
            messagebox.showerror("Admin Launch Failed", f"Unable to relaunch as administrator:\n{e}")
            return False

    def get_serial_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def populate_serial_ports(self):
        ports = self.get_serial_ports()
        self.tx_port_combo["values"] = ports
        self.rx_port_combo["values"] = ports
        if ports:
            if self.tx_port_var.get() not in ports:
                self.tx_port_var.set(ports[0])
            if self.rx_port_var.get() not in ports:
                self.rx_port_var.set(ports[1] if len(ports) > 1 else ports[0])

    def refresh_serial_ports(self):
        ports = self.get_serial_ports()
        self.populate_serial_ports()
        if ports:
            messagebox.showinfo("Serial Ports Refreshed", "Detected serial ports:\n\n" + "\n".join(ports))
        else:
            messagebox.showwarning("Serial Ports", "No serial ports detected.")

    def list_available_ports(self):
        ports = serial.tools.list_ports.comports()
        if not ports:
            messagebox.showinfo("Available Ports", "No serial ports found.")
            return
        port_list = "\n".join([f"{port.device}: {port.description}" for port in ports])
        messagebox.showinfo("Available Ports", f"Available serial ports:\n\n{port_list}")

    def disconnect_ports(self):
        self.rx_running = False
        if self.rx_thread:
            self.rx_thread.join(timeout=0.5)

        if self.tx_serial and self.tx_serial.is_open:
            self.tx_serial.close()
        if self.rx_serial and self.rx_serial.is_open:
            self.rx_serial.close()

        self.connect_button.config(text="Connect", command=self.connect_ports)
        self.tx_status.config(text="TX: Disconnected", fg="red")
        self.rx_status.config(text="RX: Disconnected", fg="red")
        self.transfer_status.config(text="Idle", fg="blue")
        self.add_tx_log("Disconnected.")
        self.add_rx_log("Disconnected.")

    def apply_frequency(self):
        freq = self.freq_entry.get().strip()
        if not freq.isdigit():
            messagebox.showwarning("Invalid Frequency", "Enter a frequency between 1 and 50000 Hz.")
            return
        frequency = int(freq)
        if frequency < 1 or frequency > MAX_FREQUENCY_HZ:
            messagebox.showwarning("Invalid Frequency", "Frequency must be between 1 and 50000 Hz.")
            return
        self.set_frequency(frequency)
        self.transfer_status.config(text=f"Frequency set to {frequency} Hz", fg="blue")

    def set_frequency(self, frequency):
        cmd = f"FREQ={frequency}\n".encode("ascii")
        if self.tx_serial and self.tx_serial.is_open:
            try:
                self.tx_serial.write(cmd)
                self.tx_serial.flush()
                self.add_tx_log(f"Sent TX frequency command: {cmd.decode().strip()}")
            except Exception as e:
                self.add_tx_log(f"Failed to set TX frequency: {e}")
        if self.rx_serial and self.rx_serial.is_open:
            try:
                self.rx_serial.write(cmd)
                self.rx_serial.flush()
                self.add_tx_log(f"Sent RX frequency command: {cmd.decode().strip()}")
            except Exception as e:
                self.add_tx_log(f"Failed to set RX frequency: {e}")

    def update_rx_debug(self):
        if self.rx_serial and self.rx_serial.is_open:
            debug_flag = 1 if self.debug_enabled.get() else 0
            cmd = f"DEBUG={debug_flag}\n".encode("ascii")
            try:
                self.rx_serial.write(cmd)
                self.rx_serial.flush()
                self.add_tx_log(f"Sent RX debug command: {cmd.decode().strip()}")
            except Exception as e:
                self.add_tx_log(f"Failed to set RX debug mode: {e}")

    def get_frequency_value(self):
        try:
            return max(1, int(self.freq_entry.get().strip()))
        except Exception:
            return 500

    def estimate_optical_frame_seconds(self, payload_len, preamble_count=16, crc_header=True):
        # TX sendManchesterByte() sends 10 Manchester bit periods per byte:
        # start + 8 data bits + stop.
        # The updated TX also inserts a short low idle gap of halfBitUs after each payload byte
        # for receiver resync stability, so include ~0.5 bit-period per payload byte.
        freq = self.get_frequency_value()
        header_len = 6 if crc_header else 4
        total_bytes = preamble_count + header_len + payload_len
        optical_seconds = (total_bytes * 10.0 / freq) + (payload_len * 0.5 / freq)
        # Extra margin prevents false timeout when Serial progress printing or OS scheduling adds delay.
        return optical_seconds + 10.0

    def format_eta(self, seconds):
        if seconds is None or seconds < 0:
            return "--:--"
        seconds = int(seconds + 0.5)
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{sec:02d}"
        return f"{minutes:02d}:{sec:02d}"

    def reset_transfer_progress(self, total_bytes=0, label="Transfer"):
        self.transfer_start_time = time.time()
        self.transfer_total_bytes = max(0, int(total_bytes or 0))
        self.transfer_done_bytes = 0
        self.progress_var.set(0.0)
        if self.transfer_total_bytes:
            self.progress_label_var.set(f"{label}: 0/{self.transfer_total_bytes} bytes | ETA --:--")
        else:
            self.progress_label_var.set(f"{label}: starting...")
        self.update_idletasks()

    def update_transfer_progress(self, done_bytes, total_bytes=None, label="Transfer"):
        if total_bytes is not None:
            self.transfer_total_bytes = max(0, int(total_bytes or 0))
        self.transfer_done_bytes = max(0, int(done_bytes or 0))

        total = self.transfer_total_bytes
        done = self.transfer_done_bytes
        if total > 0:
            percent = min(100.0, max(0.0, (done / total) * 100.0))
            elapsed = max(0.001, time.time() - (self.transfer_start_time or time.time()))
            rate = done / elapsed if done > 0 else 0
            eta = (total - done) / rate if rate > 0 else None
            self.progress_var.set(percent)
            self.progress_label_var.set(f"{label}: {done}/{total} bytes ({percent:.1f}%) | ETA {self.format_eta(eta)}")
        else:
            self.progress_var.set(0.0)
            self.progress_label_var.set(f"{label}: {done} bytes")
        self.update_idletasks()

    def finish_transfer_progress(self, label="Transfer complete"):
        self.progress_var.set(100.0)
        total = self.transfer_total_bytes
        done = self.transfer_done_bytes or total
        elapsed = time.time() - self.transfer_start_time if self.transfer_start_time else 0
        if total:
            self.progress_label_var.set(f"{label}: {done}/{total} bytes | elapsed {self.format_eta(elapsed)}")
        else:
            self.progress_label_var.set(label)
        self.update_idletasks()

    def handle_tx_status_line(self, line):
        # TX sends lines like: TX_FILE_PROGRESS: 128/2652
        if line.startswith("TX_FILE_PROGRESS:"):
            try:
                progress = line.split(":", 1)[1].strip()
                done_s, total_s = progress.split("/", 1)
                self.update_transfer_progress(int(done_s), int(total_s), "Optical TX")
            except Exception:
                pass

    def wait_for_tx_marker(self, markers, timeout_s, context="TX"):
        if isinstance(markers, str):
            markers = [markers]
        if not self.tx_serial or not self.tx_serial.is_open:
            return False

        deadline = time.time() + timeout_s
        old_timeout = self.tx_serial.timeout
        self.tx_serial.timeout = 0.25
        try:
            while time.time() < deadline:
                try:
                    raw = self.tx_serial.readline()
                except Exception as e:
                    self.add_tx_log(f"{context}: error while waiting for TX response: {e}")
                    return False
                if not raw:
                    self.update_idletasks()
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self.add_tx_log(line)
                    self.handle_tx_status_line(line)
                if any(marker in line for marker in markers):
                    return True
        finally:
            self.tx_serial.timeout = old_timeout

        self.add_tx_log(f"{context}: timeout waiting for TX done marker")
        return False

    def send_text(self):
        if not self.tx_serial or not self.tx_serial.is_open:
            messagebox.showwarning("Not Connected", "Connect TX before sending text.")
            return

        text = self.send_text_box.get("1.0", tk.END).strip()
        if not text:
            return

        # Send the whole text as one CRC-protected frame.
        # This avoids the old problem where a paragraph split across chunks could be
        # displayed late or merged with the next transmission if one chunk was missed.
        data = (text + "\n").encode("utf-8")
        size = len(data)
        if size > TEXT_FRAME_MAX:
            messagebox.showerror("Text Too Large", "Maximum supported text size is 65535 bytes.")
            return

        crc = crc16_ccitt(data)
        header = bytes([
            HEADER_START,
            0x02,
            (size >> 8) & 0xFF,
            size & 0xFF,
            (crc >> 8) & 0xFF,
            crc & 0xFF,
        ])

        self.reset_transfer_progress(size, "Text TX")
        try:
            self.tx_serial.write(header)
            self.tx_serial.flush()
            self.tx_serial.write(data)
            self.tx_serial.flush()
            self.add_tx_log(f"Queued text to TX ESP32 ({size} bytes), crc=0x{crc:04X}")
            self.transfer_status.config(text="Optical TX sending text...", fg="orange")

            timeout_s = self.estimate_optical_frame_seconds(size, preamble_count=16, crc_header=True)
            ok = self.wait_for_tx_marker("TX: text frame sent", timeout_s, "Text transfer")
            if ok:
                self.finish_transfer_progress("Text TX complete")
                self.add_tx_log(f"Sent text ({len(text)} chars, {size} bytes), crc=0x{crc:04X}")
                self.transfer_status.config(text="Text sent", fg="blue")
            else:
                self.transfer_status.config(text="TX timeout", fg="red")
        except Exception as e:
            self.add_tx_log(f"TX error sending text: {e}")
            self.transfer_status.config(text="TX error", fg="red")

    def send_file(self):
        if not self.tx_serial or not self.tx_serial.is_open:
            messagebox.showwarning("Not Connected", "Connect TX before sending a file.")
            return

        path = filedialog.askopenfilename(title="Select file to send")
        if not path:
            return

        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as e:
            messagebox.showerror("File Error", f"Unable to read file: {e}")
            return

        size = len(data)
        if size > 0xFFFF:
            messagebox.showerror("File Too Large", "Maximum supported file size is 65535 bytes.")
            return

        self.receive_file_extension = os.path.splitext(path)[1] or ".bin"
        self.pending_file_name = os.path.basename(path)
        self.reset_transfer_progress(size, "File TX")

        if self.crc_enabled.get():
            crc = crc16_ccitt(data)
            header = bytes([
                HEADER_START,
                0x01,
                (size >> 8) & 0xFF,
                size & 0xFF,
                (crc >> 8) & 0xFF,
                crc & 0xFF,
            ])
            crc_note = f", crc=0x{crc:04X}"
            done_marker = "TX: file stream sent (CRC)"
            preamble_count = 4
        else:
            header = bytes([
                HEADER_START,
                0x00,
                (size >> 8) & 0xFF,
                size & 0xFF,
            ])
            crc_note = ""
            done_marker = "TX: file stream sent (no CRC)"
            preamble_count = 4

        try:
            self.tx_serial.write(header)
            self.tx_serial.flush()
            self.tx_serial.write(data)
            self.tx_serial.flush()
            self.add_tx_log(f"Queued file '{self.pending_file_name}' to TX ESP32 ({size} bytes){crc_note}")
            self.transfer_status.config(text="Optical TX sending file...", fg="orange")

            timeout_s = self.estimate_optical_frame_seconds(size, preamble_count=preamble_count, crc_header=self.crc_enabled.get())
            ok = self.wait_for_tx_marker(done_marker, timeout_s, "File transfer")
            if ok:
                self.finish_transfer_progress("File TX complete")
                self.add_tx_log(f"Sent file '{self.pending_file_name}' ({size} bytes){crc_note}")
                self.transfer_status.config(text="Waiting for RX file start...", fg="orange")
            else:
                self.transfer_status.config(text="TX timeout", fg="red")
        except Exception as e:
            self.add_tx_log(f"TX error sending file: {e}")
            self.transfer_status.config(text="TX error", fg="red")

    def rx_loop(self):
        while self.rx_running and self.rx_serial and self.rx_serial.is_open:
            try:
                chunk = self.rx_serial.read(1024)
            except Exception as e:
                self.add_rx_log(f"RX read error: {e}")
                break

            if not chunk:
                continue

            self.receive_buffer.extend(chunk)
            self.process_receive_buffer()

        self.add_rx_log("RX monitoring stopped.")

    def process_receive_buffer(self):
        while self.receive_buffer:
            if self.expecting_file and len(self.received_file_bytes) < self.expected_file_size:
                needed = self.expected_file_size - len(self.received_file_bytes)
                take = min(needed, len(self.receive_buffer))
                self.received_file_bytes.extend(self.receive_buffer[:take])
                del self.receive_buffer[:take]
                self.add_rx_log(f"Receiving file bytes: {len(self.received_file_bytes)}/{self.expected_file_size}")
                self.update_transfer_progress(len(self.received_file_bytes), self.expected_file_size, "File RX")

                if len(self.received_file_bytes) == self.expected_file_size:
                    self.save_received_file()
                continue

            if self.expecting_text and len(self.received_text_bytes) < self.expected_text_size:
                needed = self.expected_text_size - len(self.received_text_bytes)
                take = min(needed, len(self.receive_buffer))
                self.received_text_bytes.extend(self.receive_buffer[:take])
                del self.receive_buffer[:take]
                self.update_transfer_progress(len(self.received_text_bytes), self.expected_text_size, "Text RX")

                if len(self.received_text_bytes) == self.expected_text_size:
                    self.display_received_text()
                    # RX sends one newline delimiter after the raw text. Discard it so it
                    # does not appear as an extra blank log line before RX_TEXT_CRC_OK.
                    if self.receive_buffer.startswith(b"\r\n"):
                        del self.receive_buffer[:2]
                    elif self.receive_buffer.startswith(b"\n"):
                        del self.receive_buffer[:1]
                continue

            newline_index = self.receive_buffer.find(b"\n")
            if newline_index < 0:
                break

            line = self.receive_buffer[:newline_index + 1]
            del self.receive_buffer[:newline_index + 1]
            self.handle_rx_line(line.rstrip(b"\r\n"))

    def handle_rx_line(self, line):
        try:
            text = line.decode("utf-8", errors="replace")
        except Exception:
            text = repr(line)

        if text.startswith("RX_ERROR"):
            self.add_rx_log(text)
            self.transfer_status.config(text="RX error", fg="red")
            return

        self.add_rx_log(text)

        if text.startswith("RX_FILE_PROGRESS:"):
            progress = text.split(":", 1)[1].strip()
            self.transfer_status.config(text=f"Receiving file {progress}", fg="blue")
            try:
                done_s, total_s = progress.split("/", 1)
                self.update_transfer_progress(int(done_s), int(total_s), "Optical RX")
            except Exception:
                pass
            return

        if text.startswith("RX_TEXT_PROGRESS:"):
            progress = text.split(":", 1)[1].strip()
            self.transfer_status.config(text=f"Receiving text {progress}", fg="blue")
            try:
                done_s, total_s = progress.split("/", 1)
                self.update_transfer_progress(int(done_s), int(total_s), "Optical RX")
            except Exception:
                pass
            return

        if text.startswith("RX_TEXT_START:"):
            try:
                size = int(text.split(":", 1)[1])
                self.expected_text_size = size
                self.received_text_bytes = bytearray()
                self.expecting_text = True
                self.reset_transfer_progress(size, "Text RX")
                self.add_rx_log(f"Text transfer started: {size} bytes")
                self.transfer_status.config(text="Receiving text...", fg="blue")
            except ValueError:
                self.add_rx_log("RX warning: invalid text start message")
            return

        if text.startswith("RX_TEXT_CRC_OK"):
            self.add_rx_log("RX text CRC OK")
            self.transfer_status.config(text="Text transfer CRC OK", fg="green")
            return

        if text.startswith("RX_TEXT_COMPLETE"):
            if self.expecting_text and len(self.received_text_bytes) == self.expected_text_size:
                self.display_received_text()
            elif self.expecting_text:
                self.add_rx_log("RX warning: text complete marker received before full payload")
                self.expecting_text = False
            else:
                self.transfer_status.config(text="Text transfer complete", fg="green")
            return

        if text.startswith("RX_FILE_START:"):
            try:
                size = int(text.split(":", 1)[1])
                self.expected_file_size = size
                self.received_file_bytes = bytearray()
                self.expecting_file = True
                self.reset_transfer_progress(size, "File RX")
                self.add_rx_log(f"File transfer started: {size} bytes")
                self.transfer_status.config(text="Receiving file...", fg="blue")
            except ValueError:
                self.add_rx_log("RX warning: invalid file start message")

        elif text.startswith("RX_FILE_COMPLETE"):
            if self.expecting_file and len(self.received_file_bytes) == self.expected_file_size:
                self.save_received_file()
            elif self.expecting_file:
                self.add_rx_log("RX warning: file complete marker received before full payload")
                self.expecting_file = False
            else:
                self.transfer_status.config(text="File transfer complete", fg="green")

        elif text.startswith("RX_FILE_CRC_OK"):
            self.add_rx_log("RX file CRC OK")
            self.transfer_status.config(text="File transfer CRC OK", fg="green")

        elif text.startswith("RX_FILE_CRC_FAIL"):
            self.add_rx_log(text)
            self.transfer_status.config(text="File CRC mismatch", fg="red")

        elif text.startswith("RX_TEXT_CRC_FAIL"):
            self.add_rx_log(text)
            self.transfer_status.config(text="Text CRC fail", fg="red")

    def display_received_text(self):
        try:
            decoded = self.received_text_bytes.decode("utf-8", errors="replace")
        except Exception:
            decoded = safe_str(self.received_text_bytes)

        # Display the received text as received, but keep the GUI's timestamp/prefix style.
        for line in decoded.rstrip("\r\n").splitlines():
            self.add_rx_log(f"RX: {line}")

        self.finish_transfer_progress("Text RX complete")
        self.transfer_status.config(text="Received text", fg="green")
        self.expecting_text = False
        self.expected_text_size = 0
        self.received_text_bytes = bytearray()

    def save_received_file(self):
        filename = f"received_{int(time.time())}{self.receive_file_extension}"
        full_path = os.path.join(self.receive_folder, filename)
        try:
            with open(full_path, "wb") as f:
                f.write(self.received_file_bytes)
            self.last_received_file = full_path
            self.add_rx_log(f"Saved received file: {full_path}")
            self.finish_transfer_progress("File RX complete")
            self.transfer_status.config(text=f"Received file saved", fg="green")
        except Exception as e:
            self.add_rx_log(f"Failed to save received file: {e}")
            self.transfer_status.config(text="Save failed", fg="red")
        finally:
            self.expecting_file = False
            self.received_file_bytes = bytearray()
            self.expected_file_size = 0

    def add_tx_log(self, message):
        self.tx_log.configure(state="normal")
        self.tx_log.insert(tk.END, f"{time.strftime('%H:%M:%S')} TX: {message}\n")
        self.tx_log.see(tk.END)
        self.tx_log.configure(state="disabled")

    def add_rx_log(self, message):
        self.rx_log.configure(state="normal")
        self.rx_log.insert(tk.END, f"{time.strftime('%H:%M:%S')} RX: {message}\n")
        self.rx_log.see(tk.END)
        self.rx_log.configure(state="disabled")

    def clear_tx_log(self):
        self.tx_log.configure(state="normal")
        self.tx_log.delete("1.0", tk.END)
        self.tx_log.configure(state="disabled")

    def clear_rx_log(self):
        self.rx_log.configure(state="normal")
        self.rx_log.delete("1.0", tk.END)
        self.rx_log.configure(state="disabled")

    def open_receive_folder(self):
        folder = self.receive_folder_entry.get().strip()
        if os.path.isdir(folder):
            try:
                if os.name == "nt":
                    os.startfile(folder)
                elif os.name == "posix":
                    os.system(f"xdg-open '{folder}'")
            except Exception as e:
                messagebox.showerror("Open Folder", str(e))
        else:
            messagebox.showwarning("Folder Missing", "Receive folder does not exist.")

    def on_close(self):
        self.disconnect_ports()
        self.destroy()


if __name__ == "__main__":
    app = FileTransferGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
