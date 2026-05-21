# Research Instruments

## Hardware Instruments

- ESP32 development boards for transmitter and receiver firmware.
- 2N3904 BJT stage for transmitter drive interfacing.
- IRF540N N-channel MOSFET for switching the 12 V LED load.
- 12 V DC LED bulb as the visible-light transmitter.
- BPW34 photodiode as the optical receiver sensor.
- OPA2604 operational amplifier configured as a transimpedance amplifier stage.
- LM393 comparator for converting the analog receiver signal into a digital waveform.
- 10 kOhm potentiometer or threshold divider for comparator reference adjustment.
- 12 V DC supply for LED power.
- 3.3 V ESP32 logic supply.
- Breadboard or soldered prototype board.
- Jumper wires and common-ground wiring.
- Digital multimeter for DC voltage checks.
- Oscilloscope or logic analyzer, if available, for waveform and timing verification.

## Software Instruments

- Arduino IDE or Arduino CLI for compiling and uploading ESP32 firmware.
- Python 3 for TX/RX GUI execution and data handling.
- Tkinter/customtkinter and PySerial for serial-port GUI control.
- React.js/Vite web app for diagrams, system flow, and thesis communication.
- Git and GitHub for version control and collaborative continuity.
- VS Code or equivalent IDE for firmware, GUI, and thesis editing.

## Firmware And Application Artifacts

- `working_setup/firmware/tx/tx.ino`
- `working_setup/firmware/rx/rx.ino`
- `working_setup/gui/Tx_gui.py`
- `working_setup/gui/Rx_gui.py`
- root launchers: `Tx_gui.py` and `Rx_gui.py`

## Measurement Data To Record

- TX/RX frequency setting.
- Computed `halfBitUs`.
- Comparator threshold voltage.
- BPW34/TIA signal minimum and maximum voltage.
- LM393 output logic polarity.
- Distance and alignment between LED and photodiode.
- Ambient-light condition.
- Payload type and payload length.
- Number of transmitted bits.
- Number of received bit errors.
- Bit error rate.
- CRC pass/fail count.
- Observed unstable Manchester bit count.

## Core Formulas For Experiments

Manchester half-bit timing:

```text
halfBitUs = 1,000,000 / (2 * frequencyHz)
```

Approximate Manchester optical symbol rate:

```text
half-bit transitions per second = 2 * frequencyHz
```

Raw payload bit count:

```text
payload_bits = payload_bytes * 8
```

Measured bit error rate:

```text
BER = bit_errors / total_received_bits
```

Frame success rate:

```text
frame_success_rate = passed_crc_frames / total_received_frames
```
