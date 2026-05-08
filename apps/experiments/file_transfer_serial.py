import argparse
import os
import serial
import time

BAUDRATE = 115200

HEADER_START = 0x02


def set_frequency(port, frequency):
    cmd = f"FREQ={frequency}\n".encode("ascii")
    port.write(cmd)
    port.flush()
    time.sleep(0.1)


def send_file(tx_port, file_path, frequency=1000, chunk_size=64):
    with open(file_path, "rb") as f:
        data = f.read()

    size = len(data)
    if size > 0xFFFF:
        raise ValueError("File too large: maximum supported size is 65535 bytes")

    set_frequency(tx_port, frequency)
    time.sleep(0.05)

    tx_port.write(bytes([HEADER_START, (size >> 8) & 0xFF, size & 0xFF]))
    tx_port.flush()

    for start in range(0, size, chunk_size):
        chunk = data[start:start + chunk_size]
        tx_port.write(chunk)
        tx_port.flush()
        time.sleep(0.01)

    print(f"Sent {size} bytes from {os.path.basename(file_path)}")


def receive_file(rx_port, size, output_path, timeout=10):
    rx_port.timeout = 1
    received = 0
    with open(output_path, "wb") as f:
        end_time = time.time() + timeout
        while received < size and time.time() < end_time:
            chunk = rx_port.read(size - received)
            if not chunk:
                continue
            f.write(chunk)
            received += len(chunk)
            print(f"Received {received}/{size} bytes", end="\r")

    if received != size:
        raise TimeoutError(f"Expected {size} bytes but received {received}")

    print(f"\nSaved received file to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="LiFi raw binary file transfer over serial + Manchester TX/RX")
    parser.add_argument("--tx-port", required=True, help="Serial port connected to the TX Arduino")
    parser.add_argument("--rx-port", required=True, help="Serial port connected to the RX ESP32")
    parser.add_argument("--file", required=True, help="Binary file to send")
    parser.add_argument("--out", required=True, help="Output path for received file")
    parser.add_argument("--freq", type=int, default=1000, help="Manchester bit frequency (Hz)")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        raise FileNotFoundError(args.file)

    with serial.Serial(args.tx_port, BAUDRATE, timeout=1) as tx_port, serial.Serial(args.rx_port, BAUDRATE, timeout=1) as rx_port:
        time.sleep(2)
        send_file(tx_port, args.file, frequency=args.freq)

        expected_size = os.path.getsize(args.file)
        receive_file(rx_port, expected_size, args.out)


if __name__ == "__main__":
    main()
