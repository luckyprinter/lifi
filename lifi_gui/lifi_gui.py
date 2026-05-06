import customtkinter as ctk
import serial
import threading
import time
import os
from datetime import datetime
from tkinter import messagebox

ctk.set_appearance_mode("dark")

BAUDRATE = 115200
DEFAULT_FREQUENCY_HZ = 500

class LiFiGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LiFi System (REAL MODE)")
        self.geometry("1000x700")

        self.tx = None
        self.rx = None
        self.running = True
        self.current_frequency_hz = DEFAULT_FREQUENCY_HZ

        self.receive_folder = os.path.expanduser("~/Documents/LiFi_Received")
        os.makedirs(self.receive_folder, exist_ok=True)

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=20, pady=10)

        send = ctk.CTkFrame(main)
        send.pack(side="left", fill="both", expand=True, padx=10)

        recv = ctk.CTkFrame(main)
        recv.pack(side="right", fill="both", expand=True, padx=10)

        port_frame = ctk.CTkFrame(send)
        port_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(port_frame, text="TX Port:").grid(row=0, column=0, sticky="w")
        self.tx_port_entry = ctk.CTkEntry(port_frame)
        self.tx_port_entry.insert(0, "/dev/ttyUSB0")
        self.tx_port_entry.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(port_frame, text="RX Port:").grid(row=1, column=0, sticky="w")
        self.rx_port_entry = ctk.CTkEntry(port_frame)
        self.rx_port_entry.insert(0, "/dev/ttyUSB1")
        self.rx_port_entry.grid(row=1, column=1, sticky="ew")

        port_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(port_frame, text="Connect", command=self.connect).grid(row=0, column=2, rowspan=2, padx=10)

        freq_frame = ctk.CTkFrame(send)
        freq_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(freq_frame, text="Frequency (Hz):").grid(row=0, column=0, sticky="w")
        self.frequency_entry = ctk.CTkEntry(freq_frame)
        self.frequency_entry.insert(0, str(self.current_frequency_hz))
        self.frequency_entry.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ctk.CTkButton(freq_frame, text="Apply", command=self.apply_frequency).grid(row=0, column=2, padx=10)
        freq_frame.grid_columnconfigure(1, weight=1)

        self.frequency_label = ctk.CTkLabel(send, text=self.get_frequency_label())
        self.frequency_label.pack(fill="x", padx=5, pady=(0, 10))

        self.input = ctk.CTkTextbox(send, height=120)
        self.input.pack(fill="x", pady=5)

        ctk.CTkButton(send, text="Send Text", command=self.send_text).pack(pady=2)
        ctk.CTkButton(send, text="Attach Image", command=self.unsupported_feature, state="disabled").pack(pady=2)
        ctk.CTkButton(send, text="Send Image", command=self.unsupported_feature, state="disabled").pack(pady=2)
        ctk.CTkButton(send, text="Attach Audio", command=self.unsupported_feature, state="disabled").pack(pady=2)
        ctk.CTkButton(send, text="Send Audio", command=self.unsupported_feature, state="disabled").pack(pady=2)

        ctk.CTkLabel(send, text="Only text transmission is supported by current microcontroller firmware.", text_color="orange").pack(pady=5)

        self.progress = ctk.CTkProgressBar(send)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=10, pady=5)

        self.progress_label = ctk.CTkLabel(send, text="Idle")
        self.progress_label.pack()

        self.log_box = ctk.CTkTextbox(recv, state="disabled")
        self.log_box.pack(fill="both", expand=True)

    def connect(self):
        tx_port = self.tx_port_entry.get().strip()
        rx_port = self.rx_port_entry.get().strip()
        try:
            if self.tx:
                self.tx.close()
            if self.rx:
                self.rx.close()
            self.tx = serial.Serial(tx_port, BAUDRATE, timeout=1)
            self.rx = serial.Serial(rx_port, BAUDRATE, timeout=1)
            threading.Thread(target=self.rx_loop, daemon=True).start()
            self.send_frequency_setting()
            self.log("✅ Connected")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {e}")
            self.log(f"❌ Connection failed: {e}")

    def get_frequency_label(self):
        full_bit_ms = 1000.0 / self.current_frequency_hz
        half_bit_us = 500000.0 / self.current_frequency_hz
        return f"Current frequency: {self.current_frequency_hz} Hz | Full bit: {full_bit_ms:.3f} ms | Half bit: {half_bit_us:.0f} µs"

    def apply_frequency(self):
        try:
            freq = int(self.frequency_entry.get().strip())
        except ValueError:
            messagebox.showerror("Value Error", "Please enter a valid integer frequency value.")
            return
        if freq <= 0:
            messagebox.showerror("Value Error", "Frequency must be greater than 0.")
            return
        self.current_frequency_hz = freq
        self.frequency_label.configure(text=self.get_frequency_label())
        self.send_frequency_setting()

    def send_frequency_setting(self):
        if not self.tx and not self.rx:
            return
        command = f"FREQ={self.current_frequency_hz}\n".encode('utf-8')
        try:
            if self.tx:
                self.tx.write(command)
                self.tx.flush()
            if self.rx:
                self.rx.write(command)
                self.rx.flush()
            self.log(f"🔧 Frequency set to {self.current_frequency_hz} Hz")
        except Exception as e:
            self.log(f"❌ Frequency send error: {e}")

    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def rx_loop(self):
        while self.running:
            if self.rx and self.rx.in_waiting:
                try:
                    line = self.rx.readline().decode('utf-8', errors='replace').strip()
                except Exception as e:
                    self.log(f"❌ RX read error: {e}")
                    continue
                if line:
                    self.handle_rx_line(line)
            time.sleep(0.02)

    def handle_rx_line(self, line):
        self.log(f"🔁 {line}")

    def send_text(self):
        text = self.input.get("1.0", "end").strip()
        if not text:
            return
        if not self.tx:
            messagebox.showwarning("Not connected", "TX port is not connected.")
            return
        try:
            self.tx.write((text + "\n").encode('utf-8'))
            self.tx.flush()
            self.log(f"📤 TX: {text}")
        except Exception as e:
            self.log(f"❌ TX error: {e}")

    def unsupported_feature(self):
        messagebox.showinfo("Not supported", "Current firmware only supports text transmission over the Manchester link.")

    def on_close(self):
        self.running = False
        if self.tx:
            self.tx.close()
        if self.rx:
            self.rx.close()
        self.destroy()


if __name__ == "__main__":
    app = LiFiGUI()
    app.mainloop()
