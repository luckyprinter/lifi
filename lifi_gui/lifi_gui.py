import customtkinter as ctk
import serial
import threading
import time
import os
import io
from datetime import datetime
from tkinter import filedialog
from PIL import Image

TX_PORT = "/dev/ttyUSB0"
RX_PORT = "/dev/ttyUSB1"
BAUDRATE = 115200

ctk.set_appearance_mode("dark")


class LiFiGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LiFi System (REAL MODE)")
        self.geometry("1000x700")

        self.tx = None
        self.rx = None
        self.running = True

        self.selected_image = None
        self.receive_folder = os.getcwd()

        self.image_buffer = bytearray()
        self.receiving_image = False

        self.create_widgets()
        self.connect()

    # ---------------- UI ----------------
    def create_widgets(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=20, pady=10)

        send = ctk.CTkFrame(main)
        send.pack(side="left", fill="both", expand=True, padx=10)

        recv = ctk.CTkFrame(main)
        recv.pack(side="right", fill="both", expand=True, padx=10)

        self.input = ctk.CTkTextbox(send, height=120)
        self.input.pack(fill="x")

        ctk.CTkButton(send, text="Send Text", command=self.send_text).pack()
        ctk.CTkButton(send, text="Attach Image", command=self.select_image).pack()
        ctk.CTkButton(send, text="Send Image", command=self.send_image).pack()

        ctk.CTkButton(send, text="Receive Folder", command=self.select_folder).pack()

        self.log_box = ctk.CTkTextbox(recv)
        self.log_box.pack(fill="both", expand=True)

    # ---------------- SERIAL ----------------
    def connect(self):
        try:
            self.tx = serial.Serial(TX_PORT, BAUDRATE, timeout=1)
            self.rx = serial.Serial(RX_PORT, BAUDRATE, timeout=1)

            threading.Thread(target=self.rx_loop, daemon=True).start()

            self.log("✅ Connected")
        except:
            self.tx = None
            self.rx = None
            self.log("⚠️ No hardware detected")

    # ---------------- LOG ----------------
    def log(self, msg):
        self.log_box.insert("end", f"{msg}\n")
        self.log_box.see("end")

    # ---------------- TEXT ----------------
    def send_text(self):
        text = self.input.get("1.0", "end").strip()
        if not text:
            return

        if self.tx:
            self.tx.write(f"TXT:{text}\n".encode())

        self.log(f"📤 {text}")

    # ---------------- IMAGE ----------------
    def select_image(self):
        self.selected_image = filedialog.askopenfilename()

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.receive_folder = folder

    def prepare(self, path):
        img = Image.open(path)
        img.thumbnail((128, 128))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=40)
        return buf.getvalue()

    def chunk(self, data):
        for i in range(0, len(data), 64):
            yield data[i:i+64]

    def send_image(self):
        if not self.selected_image or not self.tx:
            return

        data = self.prepare(self.selected_image)

        self.tx.write(b"IMG_START\n")

        for c in self.chunk(data):
            self.tx.write(c)
            time.sleep(0.01)

        self.tx.write(b"IMG_END\n")

        self.log("📤 Image sent")

    # ---------------- RX ----------------
    def rx_loop(self):
        while self.running:
            try:
                if self.rx and self.rx.in_waiting:
                    data = self.rx.read(self.rx.in_waiting)
                    self.process(data)
            except:
                pass

            time.sleep(0.02)

    def process(self, data):
        if b"IMG_START" in data:
            self.receiving_image = True
            self.image_buffer.clear()
            return

        if b"IMG_END" in data:
            self.receiving_image = False

            path = os.path.join(self.receive_folder, f"rx_{int(time.time())}.jpg")

            with open(path, "wb") as f:
                f.write(self.image_buffer)

            self.log(f"✅ Saved {path}")
            return

        if self.receiving_image:
            self.image_buffer.extend(data)
            return

        text = data.decode(errors="ignore").strip()
        if text:
            self.log(text)


if __name__ == "__main__":
    app = LiFiGUI()
    app.mainloop()