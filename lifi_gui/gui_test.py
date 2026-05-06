import customtkinter as ctk
import serial
import threading
import time
import os
from tkinter import filedialog, messagebox
from datetime import datetime

ctk.set_appearance_mode("dark")

BAUDRATE = 115200

class LiFiGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LiFi System v1 (File Transfer)")
        self.geometry("1000x650")

        self.tx = None
        self.rx = None
        self.running = True
        self.current_frequency = 1000

        self.create_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------- UI ----------------

    def create_ui(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=15, pady=15)

        left = ctk.CTkFrame(main)
        left.pack(side="left", fill="both", expand=True, padx=10)

        right = ctk.CTkFrame(main)
        right.pack(side="right", fill="both", expand=True, padx=10)

        # ---- PORTS ----
        port_frame = ctk.CTkFrame(left)
        port_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(port_frame, text="TX Port").grid(row=0, column=0)
        self.tx_port = ctk.CTkEntry(port_frame)
        self.tx_port.insert(0, "/dev/ttyUSB0")
        self.tx_port.grid(row=0, column=1)

        ctk.CTkLabel(port_frame, text="RX Port").grid(row=1, column=0)
        self.rx_port = ctk.CTkEntry(port_frame)
        self.rx_port.insert(0, "/dev/ttyUSB1")
        self.rx_port.grid(row=1, column=1)

        ctk.CTkButton(port_frame, text="Connect", command=self.connect).grid(row=0, column=2, rowspan=2)

        # ---- FREQUENCY ----
        freq_frame = ctk.CTkFrame(left)
        freq_frame.pack(fill="x", pady=10)

        self.freq_entry = ctk.CTkEntry(freq_frame)
        self.freq_entry.insert(0, "1000")
        self.freq_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(freq_frame, text="Set Freq", command=self.set_freq).pack(side="left", padx=5)

        # ---- TEXT ----
        self.text_box = ctk.CTkTextbox(left, height=100)
        self.text_box.pack(fill="x", pady=5)

        ctk.CTkButton(left, text="Send Text", command=self.send_text).pack(pady=5)

        # ---- IMAGE ----
        ctk.CTkButton(left, text="Send Image", command=self.send_image).pack(pady=10)

        # ---- LOG ----
        self.log_box = ctk.CTkTextbox(right, state="disabled")
        self.log_box.pack(fill="both", expand=True)

    # ---------------- CONNECTION ----------------

    def connect(self):
        try:
            self.tx = serial.Serial(self.tx_port.get(), BAUDRATE, timeout=1)
            self.rx = serial.Serial(self.rx_port.get(), BAUDRATE, timeout=1)

            self.log("Connected to TX & RX")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------------- FREQUENCY ----------------

    def set_freq(self):
        freq = int(self.freq_entry.get())
        self.current_frequency = freq

        cmd = f"FREQ={freq}\n".encode()

        if self.tx:
            self.tx.write(cmd)

        self.log(f"Frequency set: {freq} Hz")

    # ---------------- TEXT ----------------

    def send_text(self):
        if not self.tx:
            return

        msg = self.text_box.get("1.0", "end").strip()
        if not msg:
            return

        self.tx.write((msg + "\n").encode())
        self.log(f"TX Text: {msg}")

    # ---------------- IMAGE TRANSFER ----------------

    def send_image(self):
        if not self.tx:
            return

        path = filedialog.askopenfilename()

        if not path:
            return

        with open(path, "rb") as f:
            data = f.read()

        size = len(data)

        self.log(f"Sending image: {os.path.basename(path)} ({size} bytes)")

        # command to Arduino
        self.tx.write(b"SEND_IMAGE\n")

        # send size header (2 bytes)
        self.tx.write(bytes([(size >> 8) & 0xFF, size & 0xFF]))

        # send raw bytes
        chunk_size = 64

        sent = 0

        for i in range(0, size, chunk_size):
            chunk = data[i:i+chunk_size]
            self.tx.write(chunk)
            sent += len(chunk)

            self.log_progress(sent, size)

            time.sleep(0.01)  # small pacing for stability

        self.log("Image sent complete")

    # ---------------- LOGGING ----------------

    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{datetime.now().strftime('%H:%M:%S')} {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def log_progress(self, sent, total):
        percent = int((sent / total) * 100)
        self.log(f"Progress: {percent}%")

    # ---------------- CLOSE ----------------

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