import customtkinter as ctk
import serial
import threading
import time
import os
import io
import struct
import json
from datetime import datetime
from tkinter import filedialog, messagebox
from PIL import Image

ctk.set_appearance_mode("dark")

# Packet constants
TEXT_TYPE = 0x01
IMAGE_TYPE = 0x02
AUDIO_TYPE = 0x03
HEADER_SIZE = 7
MAX_PAYLOAD = 64
START_MARKER = b'<<START>>'
END_MARKER = b'<<END>>'
BAUDRATE = 115200

def pack_packet(packet_type, seq, total, payload):
    size = len(payload)
    header = struct.pack('>BHHH', packet_type, seq, total, size)
    return header + payload

def unpack_packet(data):
    if len(data) < HEADER_SIZE:
        return None
    header = data[:HEADER_SIZE]
    payload = data[HEADER_SIZE:]
    packet_type, seq, total, size = struct.unpack('>BHHH', header)
    if len(payload) != size:
        return None
    return packet_type, seq, total, size, payload

def chunk_data(data, chunk_size=MAX_PAYLOAD):
    for i in range(0, len(data), chunk_size):
        yield data[i:i+chunk_size]


class LiFiGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LiFi System (REAL MODE)")
        self.geometry("1000x700")

        self.tx = None
        self.rx = None
        self.running = True

        # file selections
        self.selected_image = None
        self.selected_audio = None
        self.receive_folder = os.path.expanduser("~/Documents/LiFi_Received")
        os.makedirs(self.receive_folder, exist_ok=True)

        # reception buffers
        self.reception_buffers = {}
        self.current_metadata = {}

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

        # Port configuration
        port_frame = ctk.CTkFrame(send)
        port_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(port_frame, text="TX Port:").grid(row=0, column=0)
        self.tx_port_entry = ctk.CTkEntry(port_frame)
        self.tx_port_entry.insert(0, "/dev/ttyUSB0")
        self.tx_port_entry.grid(row=0, column=1)
        ctk.CTkLabel(port_frame, text="RX Port:").grid(row=1, column=0)
        self.rx_port_entry = ctk.CTkEntry(port_frame)
        self.rx_port_entry.insert(0, "/dev/ttyUSB1")
        self.rx_port_entry.grid(row=1, column=1)
        ctk.CTkButton(port_frame, text="Connect", command=self.connect).grid(row=0, column=2, rowspan=2, padx=10)

        self.input = ctk.CTkTextbox(send, height=120)
        self.input.pack(fill="x", pady=5)

        ctk.CTkButton(send, text="Send Text", command=self.send_text).pack(pady=2)
        ctk.CTkButton(send, text="Attach Image", command=self.select_image).pack(pady=2)
        ctk.CTkButton(send, text="Send Image", command=self.send_image).pack(pady=2)
        ctk.CTkButton(send, text="Attach Audio", command=self.select_audio).pack(pady=2)
        ctk.CTkButton(send, text="Send Audio", command=self.send_audio).pack(pady=2)

        ctk.CTkButton(send, text="Receive Folder", command=self.select_folder).pack(pady=2)

        self.progress = ctk.CTkProgressBar(send)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=10, pady=5)

        self.progress_label = ctk.CTkLabel(send, text="Idle")
        self.progress_label.pack()

        self.log_box = ctk.CTkTextbox(recv, state="disabled")
        self.log_box.pack(fill="both", expand=True)

    # ---------------- SERIAL ----------------
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
            self.log("✅ Connected")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {e}")
            self.log(f"❌ Connection failed: {e}")

    # ---------------- LOG ----------------
    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ---------------- RX LOOP ----------------
    def rx_loop(self):
        buffer = bytearray()
        while self.running:
            if self.rx and self.rx.in_waiting:
                data = self.rx.read(self.rx.in_waiting)
                buffer.extend(data)
                while True:
                    start_index = buffer.find(START_MARKER)
                    if start_index == -1:
                        buffer.clear()
                        break
                    end_index = buffer.find(END_MARKER, start_index + len(START_MARKER))
                    if end_index == -1:
                        if start_index > 0:
                            del buffer[:start_index]
                        break
                    packet_data = buffer[start_index + len(START_MARKER):end_index]
                    self.process_packets(packet_data)
                    del buffer[:end_index + len(END_MARKER)]
            time.sleep(0.02)

    # ---------------- PROCESS PACKETS ----------------
    def process_packets(self, buffer):
        offset = 0
        while offset + HEADER_SIZE <= len(buffer):
            header = buffer[offset:offset + HEADER_SIZE]
            packet_type, seq, total, size = struct.unpack('>BHHH', header)
            packet_size = HEADER_SIZE + size
            if offset + packet_size > len(buffer):
                break
            packet_data = buffer[offset:offset + packet_size]
            packet = unpack_packet(packet_data)
            if packet:
                packet_type, seq, total, size, payload = packet
                self.handle_packet(packet_type, seq, total, payload)
                offset += packet_size
            else:
                break

    def handle_packet(self, packet_type, seq, total, payload):
        key = (packet_type, total)
        if key not in self.reception_buffers:
            self.reception_buffers[key] = {}
        self.reception_buffers[key][seq] = payload

        if seq == 0 and packet_type in (IMAGE_TYPE, AUDIO_TYPE):
            try:
                meta_str = payload.decode('utf-8')
                self.current_metadata[key] = json.loads(meta_str)
            except:
                pass

        if len(self.reception_buffers[key]) == total:
            self.reconstruct_data(key)

    def reconstruct_data(self, key):
        packet_type, total = key
        buffers = self.reception_buffers[key]
        metadata = self.current_metadata.get(key, {})

        missing = [seq for seq in range(total) if seq not in buffers]
        if missing:
            self.log(f"⚠️ Missing packets: {missing}")
            del self.reception_buffers[key]
            return

        if packet_type == TEXT_TYPE:
            data = b''.join(buffers[seq] for seq in range(total))
            text = data.decode('utf-8', errors='ignore')
            self.log(f"📥 {text}")
        elif packet_type in (IMAGE_TYPE, AUDIO_TYPE):
            data = b''.join(buffers[seq] for seq in range(1, total))
            ext = 'jpg' if packet_type == IMAGE_TYPE else 'wav'
            filename = metadata.get('filename', f'received_{int(time.time())}.{ext}')
            path = os.path.join(self.receive_folder, filename)
            with open(path, 'wb') as f:
                f.write(data)
            self.log(f"✅ {'Image' if packet_type == IMAGE_TYPE else 'Audio'} saved: {path} ({len(data)} bytes)")

        del self.reception_buffers[key]
        if key in self.current_metadata:
            del self.current_metadata[key]

    # ---------------- TEXT ----------------
    def send_text(self):
        text = self.input.get("1.0", "end").strip()
        if not text:
            return

        data = text.encode('utf-8')
        chunks = list(chunk_data(data))
        packets = [pack_packet(TEXT_TYPE, i, len(chunks), chunk) for i, chunk in enumerate(chunks)]

        if self.tx:
            self.tx.write(START_MARKER)
            for packet in packets:
                self.tx.write(packet)
            self.tx.write(END_MARKER)

        self.log(f"📤 TX: {text}")

    # ---------------- IMAGE ----------------
    def select_image(self):
        path = filedialog.askopenfilename()
        if path:
            self.selected_image = path
            self.log(f"🖼️ Selected: {os.path.basename(path)}")

    def select_audio(self):
        path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if path:
            self.selected_audio = path
            self.log(f"🎵 Selected: {os.path.basename(path)}")

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.receive_folder = folder
            self.log(f"📁 RX folder: {folder}")

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
        filename = os.path.basename(self.selected_image)

        metadata = {'filename': f'received_{int(time.time())}_{filename}'}
        meta_json = json.dumps(metadata).encode('utf-8')
        data_chunks = list(chunk_data(data))
        total_packets = 1 + len(data_chunks)

        packets = [pack_packet(IMAGE_TYPE, 0, total_packets, meta_json)]
        for i, chunk in enumerate(data_chunks):
            packets.append(pack_packet(IMAGE_TYPE, i+1, total_packets, chunk))

        self.log(f"📤 Sending image ({len(data)} bytes)")

        self.tx.write(START_MARKER)
        sent = 0
        for packet in packets:
            self.tx.write(packet)
            sent += 1
            self.progress.set(sent / total_packets)
            self.progress_label.configure(text=f"{int(sent/total_packets*100)}%")
            time.sleep(0.01)
        self.tx.write(END_MARKER)

        self.log("✅ Image sent")

    def send_audio(self):
        if not self.selected_audio or not self.tx:
            return

        with open(self.selected_audio, 'rb') as f:
            data = f.read()
        filename = os.path.basename(self.selected_audio)

        metadata = {'filename': f'received_{int(time.time())}_{filename}'}
        meta_json = json.dumps(metadata).encode('utf-8')
        data_chunks = list(chunk_data(data))
        total_packets = 1 + len(data_chunks)

        packets = [pack_packet(AUDIO_TYPE, 0, total_packets, meta_json)]
        for i, chunk in enumerate(data_chunks):
            packets.append(pack_packet(AUDIO_TYPE, i+1, total_packets, chunk))

        self.log(f"📤 Sending audio ({len(data)} bytes)")

        self.tx.write(START_MARKER)
        sent = 0
        for packet in packets:
            self.tx.write(packet)
            sent += 1
            self.progress.set(sent / total_packets)
            self.progress_label.configure(text=f"{int(sent/total_packets*100)}%")
            time.sleep(0.01)
        self.tx.write(END_MARKER)

        self.log("✅ Audio sent")


if __name__ == "__main__":
    app = LiFiGUI()
    app.mainloop()