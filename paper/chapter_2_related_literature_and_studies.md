# Chapter 2 - Related Literature And Studies

This draft separates broad related literature from more specific related
studies. Use `references.md` for citation cleanup before final formatting.

## Related Literature

### 1. Visible Light Communication Standards

IEEE 802.15.7 defines physical-layer and MAC-layer behavior for short-range
optical wireless communication. It is relevant because this thesis also uses
short-range optical communication and a low-cost intensity-modulated link. The
standard gives formal context for treating VLC as a communication system rather
than only an LED blinking experiment.

Project relevance: the thesis can cite IEEE 802.15.7 to justify the VLC/OWC
domain and to compare the project with formal optical wireless systems.

### 2. LiFi As Networked Optical Wireless Communication

Haas, Yin, Wang, and Chen describe LiFi as a broader networking concept built
from visible-light and optical wireless communication. This supports the use of
the term LiFi when the project is framed as a light-based communication system,
while still distinguishing the prototype from commercial high-speed LiFi
networks.

Project relevance: the system is a low-cost educational LiFi prototype, not a
full commercial LiFi network.

### 3. VLC Concepts, Applications, And Challenges

The IEEE Communications Surveys and Tutorials survey by Ghassemlooy-related VLC
researchers, listed in the source map as "Visible Light Communication: Concepts,
Applications and Challenges," summarizes VLC concepts, applications, and
practical issues. It is useful for Chapter 2 because the current prototype faces
typical VLC challenges: line-of-sight alignment, optical noise, receiver design,
and modulation selection.

Project relevance: the thesis can use this source to frame limitations and
future work.

### 4. Manchester Encoding For Low-Cost Communication

Manchester encoding is useful because each bit contains a transition, helping
the receiver recover timing without a separate clock wire. Analog Devices
describes Manchester encoding as widely used in low-cost digital transmission.

Project relevance: the firmware uses Manchester encoding so the RX can use
transitions and half-bit sampling to decode data.

### 5. Photodiode And Transimpedance Receiver Design

Photodiode receivers often need a transimpedance amplifier to convert small
photocurrents into measurable voltage. Analog Devices and VLC TIA literature
discuss the tradeoff among feedback resistance, bandwidth, capacitance,
stability, and noise.

Project relevance: the BPW34 + OPA2604 stage is the analog front end that makes
the LM393 comparator input usable.

## Related Studies

### 1. Indoor VLC BER And OOK Performance

Research on indoor VLC performance evaluation and optimization derives BER
behavior for VLC links using OOK and channel/noise models. This is directly
related to evaluating how often this project receives incorrect bits under
different frequencies and thresholds.

Project relevance: supports the use of bit error rate as a reliability metric.

### 2. VLC High-Capacity Modulation Survey

Surveys of VLC modulation techniques show that OOK is a simple baseline while
more advanced methods can increase throughput at the cost of complexity. This is
important because this thesis intentionally starts with a simple low-cost
physical layer before attempting image, audio, or video payloads.

Project relevance: supports the decision to begin with OOK/Manchester before
more complex modulation.

### 3. Transimpedance Amplifier Noise And Bandwidth In VLC

VLC receiver studies on op-amp based TIAs explain that receiver bandwidth and
noise are design constraints. Higher feedback impedance may increase sensitivity
but reduce bandwidth or stability; lower impedance may improve speed but reduce
voltage gain.

Project relevance: helps explain why the receiver circuit may work at one
frequency and fail at a higher frequency.

### 4. IEEE 802.15.7 SDR Implementation

An SDR implementation based on IEEE 802.15.7 demonstrates how standard VLC ideas
can be prototyped in software-defined form. Although this project uses ESP32 and
discrete electronics instead of SDR, it supports the method of implementing and
testing VLC physical-layer behavior experimentally.

Project relevance: supports experimental prototyping and comparison with
standardized VLC approaches.

### 5. LiFi/VLC Surveys On Future Applications

Recent VLC and LiFi surveys discuss optical wireless systems as complements to
RF networks, including high-speed indoor links, positioning, and secure
short-range communication. These studies help place this low-cost prototype in a
larger research field.

Project relevance: supports the future direction toward image, audio, and
possibly slow video-frame transfer.

## Formulas And Metrics For This Thesis

### Manchester Timing

The implementation uses:

```text
halfBitUs = 1,000,000 / (2 * frequencyHz)
```

This follows from Manchester coding, where one data bit is represented by two
half-bit intervals.

### Payload Bit Count

```text
payload_bits = payload_bytes * 8
```

This estimates the number of data bits before framing overhead.

### Frame Bit Estimate

For a frame with preamble, metadata, CRC, and payload:

```text
frame_bits = (preamble_bytes + header_bytes + payload_bytes) * 8
```

For Manchester optical transitions, the physical half-bit intervals are roughly:

```text
manchester_half_bits = frame_bits * 2
```

### Bit Error Rate

```text
BER = bit_errors / total_received_bits
```

In this project, bit errors may be counted by sending known test patterns and
comparing the received bitstream or decoded bytes.

### Frame Success Rate

```text
frame_success_rate = passed_crc_frames / total_received_frames
```

CRC is useful because it detects corrupted frames even when the bit error
location is not known.
