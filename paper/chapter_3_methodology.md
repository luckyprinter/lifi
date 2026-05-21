# Chapter 3 - Methodology

## Research Design

This study uses a design-and-development method. The project builds a working
LiFi prototype, tests it under controlled conditions, records transmission
results, and improves the design based on observed errors.

The first phase focuses on text transmission because text is easy to verify and
debug. Image, audio, and video are considered extension phases after the text
link is stable.

## System Architecture

The system has three major parts:

1. Transmitter subsystem
2. Optical channel
3. Receiver subsystem

The transmitter subsystem uses a Python GUI, ESP32 firmware, 2N3904, IRF540N,
and a 12 V LED bulb. The receiver subsystem uses BPW34, OPA2604, LM393, ESP32
firmware, and a Python GUI.

## Transmitter Procedure

1. Open the TX GUI.
2. Select and connect the TX ESP32 serial port.
3. Set the optical frequency.
4. Enter text or select a file payload.
5. Convert the payload into bytes.
6. Add frame metadata and CRC.
7. Send the frame to the TX ESP32 through USB serial.
8. Manchester-encode the frame in firmware.
9. Drive the 2N3904 + IRF540N circuit from GPIO5.
10. Emit the optical signal through the 12 V LED bulb.

## Receiver Procedure

1. Position the BPW34 receiver toward the LED source.
2. Adjust the OPA2604/LM393 receiver threshold until the comparator output
   toggles cleanly.
3. Open the RX GUI.
4. Select and connect the RX ESP32 serial port.
5. Set the same optical frequency used by TX.
6. Detect the Manchester start transition.
7. Sample each Manchester half-bit near its center.
8. Reconstruct bytes.
9. Validate frame CRC.
10. Display received text or save reconstructed files.

## Controlled Test Variables

- Optical frequency: `500 Hz`, `1000 Hz`, `2000 Hz`, `4000 Hz`, `9000 Hz`
- Distance between LED and photodiode
- Comparator threshold voltage
- Ambient light condition
- Payload length
- Payload type
- LED alignment

## Data Collection

For each trial, record:

- date and time
- firmware version or branch
- TX/RX frequency
- computed `halfBitUs`
- payload sent
- payload received
- CRC pass/fail
- unstable Manchester bit count if available
- comparator threshold
- observed RX voltage range
- distance and alignment
- remarks on failure behavior

## Data Analysis

The main reliability metrics are bit error rate and frame success rate.

Bit error rate:

```text
BER = bit_errors / total_received_bits
```

Frame success rate:

```text
frame_success_rate = passed_crc_frames / total_received_frames
```

Transmission time may be estimated from the number of transmitted bytes and the
selected Manchester frequency. Because Manchester uses two half-bit intervals per
data bit, higher frequency reduces transmission time but demands faster
transmitter switching, receiver bandwidth, comparator response, and sampling
accuracy.

## Development Controls

To avoid losing the working baseline:

1. Test text before changing file/image/audio/video transfer.
2. Change only one variable per experiment.
3. Record each working frequency and payload size.
4. Keep the working firmware and GUI copies in `working_setup/`.
5. Use CRC results to separate physical-layer failure from file reconstruction
   failure.

## Future Extension Method

Image transfer:

- Begin with tiny grayscale test images.
- Use small chunks such as `32` or `64` bytes.
- Increase chunk size only after CRC success is consistent.

Audio transfer:

- Start with stored tones or short audio clips.
- Use low-bitrate formats first.
- Test ADPCM or compressed audio only after raw text/image chunks are stable.

Video transfer:

- Treat real-time video as outside the first implementation.
- Test slow image sequences or very small grayscale frames as a practical thesis
  demonstration.
