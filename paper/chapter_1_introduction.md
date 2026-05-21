# Chapter 1 - Introduction

## Background Of The Study

Wireless communication is commonly associated with radio-frequency systems such
as Wi-Fi, Bluetooth, and cellular networks. However, optical wireless
communication provides another path for short-range communication by using light
as the carrier. Visible Light Communication (VLC) uses the visible portion of the
electromagnetic spectrum, commonly through LEDs whose intensity can be switched
or modulated fast enough to carry digital information.

This study focuses on a low-cost LiFi communication system using an ESP32-based
transmitter and receiver. The transmitter drives a 12 V DC LED bulb through a
2N3904 and IRF540N driver circuit. The receiver uses a BPW34 photodiode, an
OPA2604 transimpedance amplifier, and an LM393 comparator to recover the optical
signal as a digital waveform. The first goal is reliable text transmission using
Manchester encoding. Later extensions may explore image, audio, and slow-frame
video transmission.

The current design is intentionally low-cost and educational. Instead of using a
commercial optical transceiver, the system exposes the physical layer,
electronic driver, optical receiver, firmware timing, and software framing so
each bottleneck can be studied and improved.

## Statement Of The Problem

The project addresses the following question:

How can a low-cost visible light communication system reliably transmit digital
data from an ESP32 transmitter to an ESP32 receiver using a 12 V LED source and a
photodiode-comparator receiver?

Specific problems:

1. How should the transmitter and receiver timing be coordinated for Manchester
   encoded data?
2. How does the receiver circuit convert weak optical variations into a clean
   ESP32-readable digital signal?
3. What frequency range provides reliable text transfer for the current physical
   circuit?
4. How can bit error rate and CRC results be used to evaluate link reliability?
5. What transmission path is practical for later image, audio, and video
   experiments?

## Objectives Of The Study

General objective:

To design, implement, and evaluate a low-cost LiFi communication system using
visible light as the data channel.

Specific objectives:

1. Build a transmitter circuit using ESP32 GPIO output, 2N3904, IRF540N, and a
   12 V DC LED bulb.
2. Build a receiver circuit using BPW34, OPA2604 TIA, LM393 comparator, and an
   ESP32 input.
3. Implement Manchester-encoded firmware with matched transmitter and receiver
   timing.
4. Create Python GUI tools for sending, receiving, logging, and debugging data.
5. Measure reliability at selected frequencies such as 500 Hz, 1000 Hz, 2000 Hz,
   4000 Hz, and 9000 Hz.
6. Document the system using flowcharts, schematic views, and a web-based visual
   planner.

## Significance Of The Study

This project is useful for students and researchers who want to understand the
practical relationship between communication theory and low-cost electronics.
The system demonstrates how digital data becomes an optical waveform, how a
photodiode receiver recovers the waveform, and why timing, polarity, threshold,
and noise margin matter.

The output may also support future thesis work on low-cost optical links,
classroom demonstrations, short-range secure communication, and embedded-system
debugging methods.

## Scope And Limitations

The study focuses on one-way communication from TX to RX. Serial USB is used only
for local control, logging, and GUI interaction. The actual data path is the
visible light channel.

The first controlled payload is text. Image, audio, and video are treated as
future extensions after text reliability is measured. Real-time video is outside
the initial scope because the expected bandwidth of the low-cost circuit is
limited.

The receiver is sensitive to LED alignment, ambient light, comparator threshold,
photodiode bias, and physical layout. Therefore, results are expected to vary
with distance, lighting condition, and circuit construction quality.
