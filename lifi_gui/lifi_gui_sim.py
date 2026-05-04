import customtkinter as ctk
import time
import threading
import os
import io
from datetime import datetime
from tkinter import filedialog
from PIL import Image

ctk.set_appearance_mode("dark")


class LiFiGUI_SIM(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LiFi System (SIM MODE)")
        self.geometry("1000x700")

        # virtual channel
        self.virtual_channel = []
        self.lock = threading.Lock()

        # image system
        self.selected_image = None
        self.send_folder = os.getcwd()
        self.receive_folder = os.getcwd()

        self.image_buffer = bytearray()
        self.receiving_image = False

        self.create_widgets()

        threading.Thread(target=self.rx_loop, daemon=True).start()

    # ---------------- UI ----------------
    def create_widgets(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=20, pady=10)

        send = ctk.CTkFrame(main)
        send.pack(side="left", fill="both", expand=True, padx=10)

        recv = ctk.CTkFrame(main)
        recv.pack(side="right", fill="both", expand=True, padx=10)

        ctk.CTkLabel(send, text="SEND", font=ctk.CTkFont(size=16)).pack()

        self.input = ctk.CTkTextbox(send, height=120)
        self.input.pack(fill="x", padx=10)

        ctk.CTkButton(send, text="Send Text", command=self.send_text).pack(pady=5)
        ctk.CTkButton(send, text="Attach Image", command=self.select_image).pack(pady=5)
        ctk.CTkButton(send, text="Send Image", command=self.send_image).pack(pady=5)

        ctk.CTkButton(send, text="Receive Folder", command=self.select_rx_folder).pack(pady=5)

        self.progress = ctk.CTkProgressBar(send)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=10, pady=10)

        self.progress_label = ctk.CTkLabel(send, text="Idle")
        self.progress_label.pack()

        ctk.CTkLabel(recv, text="RECEIVED", font=ctk.CTkFont(size=16)).pack()

        self.log_box = ctk.CTkTextbox(recv, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=10)

    # ---------------- LOG ----------------
    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ---------------- TX ----------------
    def tx(self, packet):
        time.sleep(0.05)
        with self.lock:
            self.virtual_channel.append(packet)

    # ---------------- RX LOOP ----------------
    def rx_loop(self):
        while True:
            if self.virtual_channel:
                with self.lock:
                    data = self.virtual_channel.pop(0)
                self.process(data)
            time.sleep(0.02)

    # ---------------- PROCESS ----------------
    def process(self, data):

        if b"IMG_START" in data:
            self.receiving_image = True
            self.image_buffer.clear()
            self.log("📥 Image start")
            return

        if b"IMG_END" in data:
            self.receiving_image = False

            path = os.path.join(
                self.receive_folder,
                f"received_{int(time.time())}.jpg"
            )

            with open(path, "wb") as f:
                f.write(self.image_buffer)

            self.log(f"✅ Saved: {path}")
            return

        if self.receiving_image:
            self.image_buffer.extend(data)
            return

        text = data.decode(errors="ignore").strip()
        if text:
            self.log(f"📥 {text}")

    # ---------------- TEXT ----------------
    def send_text(self):
        text = self.input.get("1.0", "end").strip()
        if not text:
            return

        self.tx(f"TXT:{text}".encode())
        self.log(f"📤 TX: {text}")

    # ---------------- IMAGE ----------------
    def select_image(self):
        path = filedialog.askopenfilename()
        if path:
            self.selected_image = path
            self.log(f"🖼️ Selected: {os.path.basename(path)}")

    def select_rx_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.receive_folder = folder
            self.log("📁 RX folder updated")

    def prepare_image(self, path):
        img = Image.open(path)
        img.thumbnail((128, 128))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=40)

        return buf.getvalue()

    def chunk(self, data, size=64):
        for i in range(0, len(data), size):
            yield data[i:i+size]

    def send_image(self):
        if not self.selected_image:
            return

        data = self.prepare_image(self.selected_image)

        self.log(f"📤 Sending image ({len(data)} bytes)")

        self.tx(b"IMG_START\n")

        sent = 0
        total = len(data)

        for c in self.chunk(data):
            self.tx(c)
            sent += len(c)

            self.progress.set(sent/total)
            self.progress_label.configure(text=f"{int(sent/total*100)}%")

            time.sleep(0.01)

        self.tx(b"\nIMG_END\n")

        self.log("✅ Image sent")


if __name__ == "__main__":
    app = LiFiGUI_SIM()
    app.mainloop()