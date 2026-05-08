import customtkinter as ctk
import serial
from serial.tools import list_ports
import threading
import time
import os
import queue
from datetime import datetime
from tkinter import messagebox

ctk.set_appearance_mode("dark")

BAUDRATE = 115200
DEFAULT_FREQUENCY_HZ = 500
MIN_FREQUENCY_HZ = 1
MAX_FREQUENCY_HZ = 10000


class LiFiGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LiFi System (Stable Text Mode)")
        self.geometry("1000x700")

        self.tx = None
        self.rx = None
        self.running = True
        self.connected = False
        self.log_queue = queue.Queue()

        self.current_frequency_hz = DEFAULT_FREQUENCY_HZ

        self.receive_folder = os.path.expanduser("~/Documents/LiFi_Received")
        os.makedirs(self.receive_folder, exist_ok=True)

        self.create_widgets()
        self.refresh_ports()
        self.after(50, self.process_log_queue)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- UI ----------------

    def create_widgets(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=20, pady=10)

        left = ctk.CTkFrame(main)
        left.pack(side="left", fill="both", expand=True, padx=10)

        right = ctk.CTkFrame(main)
        right.pack(side="right", fill="both", expand=True, padx=10)

        # -------- PORTS --------
        port_frame = ctk.CTkFrame(left)
        port_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(port_frame, text="TX Port").grid(row=0, column=0)
        self.tx_port = ctk.CTkEntry(port_frame)
        self.tx_port.insert(0, "/dev/ttyUSB0")
        self.tx_port.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(port_frame, text="RX Port").grid(row=1, column=0)
        self.rx_port = ctk.CTkEntry(port_frame)
        self.rx_port.insert(0, "/dev/ttyUSB1")
        self.rx_port.grid(row=1, column=1, sticky="ew")

        port_frame.grid_columnconfigure(1, weight=1)

        self.connect_button = ctk.CTkButton(port_frame, text="Connect", command=self.connect)
        self.connect_button.grid(row=0, column=2, padx=10)

        self.disconnect_button = ctk.CTkButton(port_frame, text="Disconnect", command=self.disconnect, state="disabled")
        self.disconnect_button.grid(row=1, column=2, padx=10)

        ctk.CTkButton(port_frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=3, rowspan=2, padx=5)

        # -------- FREQUENCY --------
        freq_frame = ctk.CTkFrame(left)
        freq_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(freq_frame, text="Frequency (Hz)").grid(row=0, column=0)

        self.freq_entry = ctk.CTkEntry(freq_frame)
        self.freq_entry.insert(0, str(self.current_frequency_hz))
        self.freq_entry.grid(row=0, column=1, sticky="ew")

        ctk.CTkButton(freq_frame, text="Apply", command=self.apply_freq).grid(row=0, column=2, padx=10)

        freq_frame.grid_columnconfigure(1, weight=1)

        self.freq_label = ctk.CTkLabel(left, text=self.freq_text())
        self.freq_label.pack(pady=5)

        # -------- TEXT INPUT --------
        self.input_box = ctk.CTkTextbox(left, height=120)
        self.input_box.pack(fill="x", pady=10)

        ctk.CTkButton(left, text="Send Text", command=self.send_text).pack()

        # disabled future features
        ctk.CTkButton(left, text="Send Image (soon)", state="disabled").pack(pady=2)
        ctk.CTkButton(left, text="Send Audio (soon)", state="disabled").pack(pady=2)

        # -------- PROGRESS --------
        self.progress = ctk.CTkProgressBar(left)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=10)

        self.status = ctk.CTkLabel(left, text="Disconnected")
        self.status.pack()

        # -------- LOG --------
        self.log_box = ctk.CTkTextbox(right, state="disabled")
        self.log_box.pack(fill="both", expand=True)

    # ---------------- CONNECTION ----------------

    def connect(self):
        if self.connected:
            self.log("Already connected")
            return

        try:
            self.tx = serial.Serial(self.tx_port.get(), BAUDRATE, timeout=1)
            self.rx = serial.Serial(self.rx_port.get(), BAUDRATE, timeout=1)

            self.connected = True
            threading.Thread(target=self.rx_loop, daemon=True).start()

            self.send_freq()

            self.connect_button.configure(state="disabled")
            self.disconnect_button.configure(state="normal")
            self.status.configure(text="Connected")
            self.log("Connected")
        except Exception as e:
            self.disconnect(log_message=False)
            messagebox.showerror("Error", str(e))
            self.log(f"Connection failed: {e}")

    def disconnect(self, log_message=True):
        self.connected = False

        for port_name in ("tx", "rx"):
            port = getattr(self, port_name)
            if port:
                try:
                    port.close()
                except Exception as e:
                    self.log(f"{port_name.upper()} close error: {e}")
                finally:
                    setattr(self, port_name, None)

        self.connect_button.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self.status.configure(text="Disconnected")

        if log_message:
            self.log("Disconnected")

    def refresh_ports(self):
        ports = [port.device for port in list_ports.comports()]
        if not ports:
            self.log("No serial ports detected; enter ports manually.")
            return

        self.log("Detected serial ports: " + ", ".join(ports))

        if self.tx_port.get() not in ports:
            self.tx_port.delete(0, "end")
            self.tx_port.insert(0, ports[0])

        if len(ports) > 1 and self.rx_port.get() not in ports:
            self.rx_port.delete(0, "end")
            self.rx_port.insert(0, ports[1])

    # ---------------- FREQUENCY ----------------

    def apply_freq(self):
        try:
            f = int(self.freq_entry.get())
            if f < MIN_FREQUENCY_HZ or f > MAX_FREQUENCY_HZ:
                raise ValueError()

            self.current_frequency_hz = f
            self.freq_label.configure(text=self.freq_text())
            self.send_freq()

        except ValueError:
            messagebox.showerror("Error", f"Frequency must be {MIN_FREQUENCY_HZ}-{MAX_FREQUENCY_HZ} Hz")

    def send_freq(self):
        cmd = f"FREQ={self.current_frequency_hz}\n".encode()

        try:
            if self.tx:
                self.tx.write(cmd)
                self.tx.flush()

            if self.rx:
                self.rx.write(cmd)
                self.rx.flush()

            self.log(f"FREQ set -> {self.current_frequency_hz} Hz")

        except Exception as e:
            self.log(f"FREQ error: {e}")

    def freq_text(self):
        full_bit = 1000 / self.current_frequency_hz
        half_bit = 500000 / self.current_frequency_hz
        return f"{self.current_frequency_hz} Hz | full {full_bit:.3f} ms | half {half_bit:.0f} µs"

    # ---------------- SEND TEXT ----------------

    def send_text(self):
        text = self.input_box.get("1.0", "end").strip()

        if not text or not self.tx:
            return

        try:
            # GUI sends raw text; TX handles Manchester encoding.
            self.tx.write((text + "\n").encode())
            self.tx.flush()

            self.log(f"TX: {text}")

        except Exception as e:
            self.log(f"TX error: {e}")

    # ---------------- RX ----------------

    def rx_loop(self):
        while self.running and self.connected:
            try:
                if self.rx and self.rx.in_waiting:
                    line = self.rx.readline().decode(errors="ignore").strip()
                    if line:
                        self.log_queue.put(f"RX: {line}")
            except Exception as e:
                self.log_queue.put(f"RX error: {e}")
                break

            time.sleep(0.02)

    # ---------------- LOG ----------------

    def process_log_queue(self):
        while not self.log_queue.empty():
            self.log(self.log_queue.get())

        if self.running:
            self.after(50, self.process_log_queue)

    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ---------------- CLOSE ----------------

    def on_close(self):
        self.running = False
        self.disconnect(log_message=False)
        self.destroy()


if __name__ == "__main__":
    app = LiFiGUI()
    app.mainloop()
