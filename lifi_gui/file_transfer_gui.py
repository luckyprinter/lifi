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
        self.title("LiFi File Transfer")
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
        self.receive_buffer = bytearray()
        self.receive_file_extension = ".bin"
        self.last_received_file = None
        self.pending_file_name = None
        self.crc_enabled = tk.BooleanVar(value=True)
        self.debug_enabled = tk.BooleanVar(value=False)

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
            self.tx_serial = serial.Serial(tx_port_name, BAUDRATE, timeout=1)
            self.rx_serial = serial.Serial(rx_port_name, BAUDRATE, timeout=0.1)
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
        self.transfer_status.config(text="Connected", fg="green")

        if freq.isdigit():
            self.apply_frequency()

        self.update_rx_debug()

        self.rx_running = True
        self.rx_thread = threading.Thread(target=self.rx_loop, daemon=True)
        self.rx_thread.start()
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
            messagebox.showwarning("Invalid Frequency", "Enter a frequency between 1 and 1000 Hz.")
            return
        frequency = int(freq)
        if frequency < 1 or frequency > 1000:
            messagebox.showwarning("Invalid Frequency", "Frequency must be between 1 and 1000 Hz.")
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

    def send_text(self):
        if not self.tx_serial or not self.tx_serial.is_open:
            messagebox.showwarning("Not Connected", "Connect TX before sending text.")
            return

        text = self.send_text_box.get("1.0", tk.END).strip()
        if not text:
            return

        data = (text + "\n").encode("utf-8")
        chunk_size = 128
        sent = 0
        try:
            while sent < len(data):
                chunk = data[sent : sent + chunk_size]
                crc = crc16_ccitt(chunk)
                header = bytes([
                    HEADER_START,
                    0x02,
                    (len(chunk) >> 8) & 0xFF,
                    len(chunk) & 0xFF,
                    (crc >> 8) & 0xFF,
                    crc & 0xFF,
                ])
                self.tx_serial.write(header)
                self.tx_serial.flush()
                self.tx_serial.write(chunk)
                self.tx_serial.flush()
                sent += len(chunk)
                if self.debug_enabled.get():
                    self.add_tx_log(f"Sent text chunk {sent}/{len(data)}")
                self.transfer_status.config(text=f"Text sending {sent}/{len(data)}", fg="blue")
                time.sleep(0.01)

            self.add_tx_log(f"Sent text ({len(text)} bytes) in {((len(data) - 1) // chunk_size) + 1} chunks")
            self.transfer_status.config(text="Text sent", fg="blue")
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

        chunk_size = 64
        sent = 0
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
        else:
            header = bytes([
                HEADER_START,
                0x00,
                (size >> 8) & 0xFF,
                size & 0xFF,
            ])
            crc = None
            crc_note = ""

        try:
            self.tx_serial.write(header)
            self.tx_serial.flush()

            for i in range(0, len(data), chunk_size):
                chunk = data[i : i + chunk_size]
                self.tx_serial.write(chunk)
                self.tx_serial.flush()
                sent += len(chunk)
                if self.debug_enabled.get():
                    self.add_tx_log(f"TX chunk sent {sent}/{size}")
                if sent % (chunk_size * 4) == 0 or sent == size:
                    self.transfer_status.config(text=f"File sending {sent}/{size}", fg="blue")
                time.sleep(0.01)

            self.add_tx_log(f"Sent file '{self.pending_file_name}' ({size} bytes){crc_note}")
            self.transfer_status.config(text=f"Waiting for RX file start...", fg="orange")
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

                if len(self.received_file_bytes) == self.expected_file_size:
                    self.save_received_file()
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
            return

        if text.startswith("RX_FILE_START:"):
            try:
                size = int(text.split(":", 1)[1])
                self.expected_file_size = size
                self.received_file_bytes = bytearray()
                self.expecting_file = True
                self.add_rx_log(f"File transfer started: {size} bytes")
                self.transfer_status.config(text="Receiving file...", fg="blue")
            except ValueError:
                self.add_rx_log("RX warning: invalid file start message")

        elif text.startswith("RX_FILE_COMPLETE"):
            if self.expecting_file and len(self.received_file_bytes) == self.expected_file_size:
                self.save_received_file()
            else:
                self.add_rx_log("RX warning: file complete marker received before full payload")
                self.expecting_file = False

        elif text.startswith("RX_FILE_CRC_OK"):
            self.add_rx_log("RX file CRC OK")
            self.transfer_status.config(text="File transfer CRC OK", fg="green")

        elif text.startswith("RX_FILE_CRC_FAIL"):
            self.add_rx_log(text)
            self.transfer_status.config(text="File CRC mismatch", fg="red")

        elif text.startswith("RX_TEXT_CRC_FAIL"):
            self.add_rx_log(text)
            self.transfer_status.config(text="Text chunk CRC fail", fg="red")

    def save_received_file(self):
        filename = f"received_{int(time.time())}{self.receive_file_extension}"
        full_path = os.path.join(self.receive_folder, filename)
        try:
            with open(full_path, "wb") as f:
                f.write(self.received_file_bytes)
            self.last_received_file = full_path
            self.add_rx_log(f"Saved received file: {full_path}")
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
