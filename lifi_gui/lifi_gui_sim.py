import customtkinter as ctk
import time
import threading
import os
import io
import struct
import json
from datetime import datetime
from tkinter import filedialog
from PIL import Image

ctk.set_appearance_mode("dark")

# Packet constants
TEXT_TYPE = 0x01
IMAGE_TYPE = 0x02
AUDIO_TYPE = 0x03
HEADER_SIZE = 7  # 1 + 2 + 2 + 2
MAX_PAYLOAD = 64
START_MARKER = b'<<START>>'
END_MARKER = b'<<END>>'

def pack_packet(packet_type, seq, total, payload):
    """Pack data into binary packet format."""
    size = len(payload)
    header = struct.pack('>BHHH', packet_type, seq, total, size)
    return header + payload

def unpack_packet(data):
    """Unpack binary packet, return (type, seq, total, size, payload)."""
    if len(data) < HEADER_SIZE:
        return None
    header = data[:HEADER_SIZE]
    payload = data[HEADER_SIZE:]
    packet_type, seq, total, size = struct.unpack('>BHHH', header)
    if len(payload) != size:
        return None
    return packet_type, seq, total, size, payload

def chunk_data(data, chunk_size=MAX_PAYLOAD):
    """Chunk data into pieces of max chunk_size."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i+chunk_size]


class LiFiGUI_SIM(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LiFi System (SIM MODE)")
        self.geometry("1000x700")

        # virtual channel
        self.virtual_channel = []
        self.lock = threading.Lock()

        # file system
        self.selected_image = None
        self.selected_audio = None
        self.send_folder = os.getcwd()
        self.receive_folder = os.path.expanduser("~/Documents/LiFi_Received")
        os.makedirs(self.receive_folder, exist_ok=True)

        # reception buffers
        self.reception_buffers = {}  # (type, total) -> {seq: payload}
        self.current_metadata = {}  # (type, total) -> metadata dict

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
        ctk.CTkButton(send, text="Attach Audio", command=self.select_audio).pack(pady=5)
        ctk.CTkButton(send, text="Send Audio", command=self.send_audio).pack(pady=5)

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
    def tx(self, data):
        """Transmit data with framing markers."""
        time.sleep(0.05)
        with self.lock:
            self.virtual_channel.append(START_MARKER)
            if isinstance(data, list):
                for packet in data:
                    self.virtual_channel.append(packet)
            else:
                self.virtual_channel.append(data)
            self.virtual_channel.append(END_MARKER)

    # ---------------- RX LOOP ----------------
    def rx_loop(self):
        buffer = bytearray()
        in_transmission = False
        while True:
            if self.virtual_channel:
                with self.lock:
                    data = self.virtual_channel.pop(0)
                if data == START_MARKER:
                    buffer.clear()
                    in_transmission = True
                elif data == END_MARKER and in_transmission:
                    in_transmission = False
                    self.process_packets(buffer)
                elif in_transmission:
                    buffer.extend(data)
            time.sleep(0.02)

    # ---------------- PROCESS PACKETS ----------------
    def process_packets(self, buffer):
        """Process received packet data."""
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
                break  # Invalid packet, stop processing

    def handle_packet(self, packet_type, seq, total, payload):
        """Handle individual packet."""
        key = (packet_type, total)
        if key not in self.reception_buffers:
            self.reception_buffers[key] = {}
        self.reception_buffers[key][seq] = payload

        # If first packet and file type, parse metadata
        if seq == 0 and packet_type in (IMAGE_TYPE, AUDIO_TYPE):
            try:
                meta_str = payload.decode('utf-8')
                self.current_metadata[key] = json.loads(meta_str)
            except:
                pass  # Ignore invalid metadata

        # Check if all packets received
        if len(self.reception_buffers[key]) == total:
            self.reconstruct_data(key)

    def reconstruct_data(self, key):
        """Reconstruct data from packets."""
        packet_type, total = key
        buffers = self.reception_buffers[key]
        metadata = self.current_metadata.get(key, {})

        # Check for missing packets
        missing = []
        for seq in range(total):
            if seq not in buffers:
                missing.append(seq)
        if missing:
            self.log(f"⚠️ Missing packets: {missing}")
            del self.reception_buffers[key]
            return

        if packet_type == TEXT_TYPE:
            data = b''.join(buffers[seq] for seq in range(total))
            text = data.decode('utf-8', errors='ignore')
            self.log(f"📥 {text}")
        elif packet_type in (IMAGE_TYPE, AUDIO_TYPE):
            data = b''.join(buffers[seq] for seq in range(1, total))  # Skip seq 0 (metadata)
            filename = metadata.get('filename', f'received_{int(time.time())}.{"jpg" if packet_type == IMAGE_TYPE else "wav"}')
            path = os.path.join(self.receive_folder, filename)
            with open(path, 'wb') as f:
                f.write(data)
            self.log(f"✅ {'Image' if packet_type == IMAGE_TYPE else 'Audio'} saved: {path} ({len(data)} bytes)")

        # Cleanup
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

        self.tx(packets)
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
            self.log(f"📁 RX folder: {folder}")

    def prepare_image(self, path):
        img = Image.open(path)
        img.thumbnail((128, 128))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=40)

        return buf.getvalue()

    def send_image(self):
        if not self.selected_image:
            return

        data = self.prepare_image(self.selected_image)
        filename = os.path.basename(self.selected_image)

        metadata = {'filename': f'received_{int(time.time())}_{filename}'}
        meta_json = json.dumps(metadata).encode('utf-8')
        data_chunks = list(chunk_data(data))
        total_packets = 1 + len(data_chunks)

        packets = [pack_packet(IMAGE_TYPE, 0, total_packets, meta_json)]
        for i, chunk in enumerate(data_chunks):
            packets.append(pack_packet(IMAGE_TYPE, i+1, total_packets, chunk))

        self.log(f"📤 Sending image ({len(data)} bytes)")

        sent = 0
        total = len(packets)
        self.tx(packets)

        for i in range(total):
            sent += 1
            self.progress.set(sent / total)
            self.progress_label.configure(text=f"{int(sent/total*100)}%")
            time.sleep(0.01)

        self.log("✅ Image sent")

    def select_audio(self):
        path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if path:
            self.selected_audio = path
            self.log(f"🎵 Selected: {os.path.basename(path)}")

    def send_audio(self):
        if not self.selected_audio:
            return

        with open(self.selected_audio, 'rb') as f:
            data = f.read()
        filename = os.path.basename(self.selected_audio)

        # Metadata in first packet
        metadata = {'filename': f'received_{int(time.time())}_{filename}'}
        meta_json = json.dumps(metadata).encode('utf-8')
        data_chunks = list(chunk_data(data))
        total_packets = 1 + len(data_chunks)

        packets = [pack_packet(AUDIO_TYPE, 0, total_packets, meta_json)]
        for i, chunk in enumerate(data_chunks):
            packets.append(pack_packet(AUDIO_TYPE, i+1, total_packets, chunk))

        self.log(f"📤 Sending audio ({len(data)} bytes)")

        sent = 0
        total = len(packets)

        self.tx(packets)

        for i in range(total):
            sent += 1
            self.progress.set(sent / total)
            self.progress_label.configure(text=f"{int(sent/total*100)}%")
            time.sleep(0.01)

        self.log("✅ Audio sent")


if __name__ == "__main__":
    app = LiFiGUI_SIM()
    app.mainloop()