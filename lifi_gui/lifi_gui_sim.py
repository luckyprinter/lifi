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
DEFAULT_FREQUENCY_HZ = 500


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


def encode_manchester_byte(byte):
    bits = []
    bits.extend([False, True])
    for i in range(7, -1, -1):
        bool_bit = (byte & (1 << i)) != 0
        bits.append(not bool_bit)
        bits.append(bool_bit)
    bits.extend([True, False])
    return bits


def encode_manchester_bytes(data):
    bits = []
    for byte in data:
        bits.extend(encode_manchester_byte(byte))
    return bits


def decode_manchester_bits(bits):
    decoded = bytearray()
    i = 0
    while i + 20 <= len(bits):
        if bits[i] != False or bits[i + 1] != True:
            i += 1
            continue

        byte_val = 0
        valid = True
        idx = i + 2
        for bit_index in range(7, -1, -1):
            first_half = bits[idx]
            second_half = bits[idx + 1]
            if first_half == second_half:
                valid = False
                break
            if second_half:
                byte_val |= 1 << bit_index
            idx += 2

        if not valid:
            i += 1
            continue

        if bits[idx] != True or bits[idx + 1] != False:
            i += 1
            continue

        decoded.append(byte_val)
        i = idx + 2

    return bytes(decoded), i


class LiFiGUI_SIM(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("LiFi System (SIM MODE)")
        self.geometry("1000x700")

        self.virtual_channel = []
        self.lock = threading.Lock()
        self.rx_buffer = bytearray()
        self.current_frequency_hz = DEFAULT_FREQUENCY_HZ

        self.selected_image = None
        self.selected_audio = None
        self.receive_folder = os.path.expanduser("~/Documents/LiFi_Received")
        os.makedirs(self.receive_folder, exist_ok=True)

        self.reception_buffers = {}
        self.current_metadata = {}

        self.create_widgets()
        threading.Thread(target=self.rx_loop, daemon=True).start()

    def create_widgets(self):
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=20, pady=10)

        send = ctk.CTkFrame(main)
        send.pack(side="left", fill="both", expand=True, padx=10)

        recv = ctk.CTkFrame(main)
        recv.pack(side="right", fill="both", expand=True, padx=10)

        ctk.CTkLabel(send, text="SEND", font=ctk.CTkFont(size=16)).pack()

        freq_frame = ctk.CTkFrame(send)
        freq_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(freq_frame, text="Frequency (Hz):").grid(row=0, column=0, sticky="w")
        self.frequency_entry = ctk.CTkEntry(freq_frame)
        self.frequency_entry.insert(0, str(self.current_frequency_hz))
        self.frequency_entry.grid(row=0, column=1, sticky="ew", padx=(5,0))
        ctk.CTkButton(freq_frame, text="Apply", command=self.apply_frequency).grid(row=0, column=2, padx=5)
        freq_frame.grid_columnconfigure(1, weight=1)

        self.frequency_label = ctk.CTkLabel(send, text=self.get_frequency_label())
        self.frequency_label.pack(fill="x", padx=10, pady=(0,10))

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

    def log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def get_frequency_label(self):
        full_bit_ms = 1000.0 / self.current_frequency_hz
        half_bit_us = 500000.0 / self.current_frequency_hz
        return f"Current frequency: {self.current_frequency_hz} Hz | Full bit: {full_bit_ms:.3f} ms | Half bit: {half_bit_us:.0f} µs"

    def apply_frequency(self):
        try:
            freq = int(self.frequency_entry.get().strip())
        except ValueError:
            self.log("❌ Invalid frequency value")
            return
        if freq <= 0:
            self.log("❌ Frequency must be greater than 0")
            return
        self.current_frequency_hz = freq
        self.frequency_label.configure(text=self.get_frequency_label())
        self.log(f"🔧 Simulator frequency set to {freq} Hz")

    def tx(self, data):
        time.sleep(0.05)
        encoded = encode_manchester_bytes(START_MARKER)
        if isinstance(data, list):
            for packet in data:
                encoded.extend(encode_manchester_bytes(packet))
        else:
            encoded.extend(encode_manchester_bytes(data))
        encoded.extend(encode_manchester_bytes(END_MARKER))
        with self.lock:
            self.virtual_channel.extend(encoded)

    def rx_loop(self):
        bit_buffer = []
        while True:
            with self.lock:
                if self.virtual_channel:
                    bit_buffer.extend(self.virtual_channel)
                    self.virtual_channel.clear()

            if bit_buffer:
                decoded_bytes, consumed = decode_manchester_bits(bit_buffer)
                if consumed > 0:
                    del bit_buffer[:consumed]
                    if decoded_bytes:
                        self.process_received_bytes(decoded_bytes)
            time.sleep(0.02)

    def process_received_bytes(self, data_bytes):
        self.rx_buffer.extend(data_bytes)

        while True:
            start_index = self.rx_buffer.find(START_MARKER)
            if start_index == -1:
                if len(self.rx_buffer) > len(START_MARKER):
                    self.rx_buffer = self.rx_buffer[-len(START_MARKER):]
                break

            end_index = self.rx_buffer.find(END_MARKER, start_index + len(START_MARKER))
            if end_index == -1:
                if start_index > 0:
                    self.rx_buffer = self.rx_buffer[start_index:]
                break

            packet_data = self.rx_buffer[start_index + len(START_MARKER):end_index]
            self.process_packets(packet_data)
            self.rx_buffer = self.rx_buffer[end_index + len(END_MARKER):]

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

    def send_text(self):
        text = self.input.get("1.0", "end").strip()
        if not text:
            return

        data = text.encode('utf-8')
        chunks = list(chunk_data(data))
        packets = [pack_packet(TEXT_TYPE, i, len(chunks), chunk) for i, chunk in enumerate(chunks)]

        self.tx(packets)
        self.log(f"📤 TX: {text}")

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

        for _ in range(total):
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

        for _ in range(total):
            sent += 1
            self.progress.set(sent / total)
            self.progress_label.configure(text=f"{int(sent/total*100)}%")
            time.sleep(0.01)

        self.log("✅ Audio sent")


if __name__ == "__main__":
    app = LiFiGUI_SIM()
    app.mainloop()
