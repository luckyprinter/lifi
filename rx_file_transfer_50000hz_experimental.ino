// RX - ESP32 Manchester File/Text Transfer Receiver (V4)
// 50 kHz experimental range.
// Supports:
//   0x00 = file without CRC
//   0x01 = file with CRC
//   0x02 = text with CRC, delivered to GUI as one length-delimited text block
// Fix: text is no longer assembled line-by-line from multiple chunks.

#include "driver/gpio.h"

#define RX_PIN 5

const uint32_t MAX_FREQUENCY_HZ = 50000;

uint32_t frequencyHz = 500;
uint32_t halfBitUs = 1000;

inline int readRxPin() {
#if defined(ARDUINO_ARCH_ESP32)
  return gpio_get_level((gpio_num_t)RX_PIN);
#else
  return digitalRead(RX_PIN);
#endif
}

enum RxState {
  WAIT_START,
  READ_TYPE,
  READ_SIZE_MSB,
  READ_SIZE_LSB,
  READ_CRC_MSB,
  READ_CRC_LSB,
  READ_DATA
};

RxState rxState = WAIT_START;
uint8_t frameType = 0;
uint16_t expectedSize = 0;
uint16_t bytesRemaining = 0;
uint16_t expectedCRC = 0;
uint16_t computedCRC = 0;
uint8_t *payloadBuffer = nullptr;
bool rxDebug = false;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);
  pinMode(RX_PIN, INPUT);

  setFrequency(frequencyHz);
  Serial.println("RX File Transfer Ready - 50 kHz experimental command-fix");
}

void loop() {
  // Always check USB serial commands. The older version could block forever
  // inside receiveManchesterByte() while waiting for optical edges, so FREQ
  // changes from the GUI were sometimes ignored.
  handleSerialCommands();

  int received = receiveManchesterByte();
  if (received < 0) {
    return;
  }

  processReceivedByte((uint8_t)received);
}

bool handleSerialCommands() {
  bool handled = false;

  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.length() == 0) {
      continue;
    }

    if (cmd.startsWith("FREQ=")) {
      setFrequency(cmd.substring(5).toInt());
      // A frequency change means the next optical frame should start cleanly.
      resetFrame();
      handled = true;
      continue;
    }

    if (cmd.startsWith("DEBUG=")) {
      rxDebug = (cmd.substring(6).toInt() != 0);
      Serial.print("RX debug ");
      Serial.println(rxDebug ? "enabled" : "disabled");
      handled = true;
      continue;
    }

    Serial.print("RX: unknown command ");
    Serial.println(cmd);
    handled = true;
  }

  return handled;
}

int receiveManchesterByte() {
  while (true) {
    // Wait for a start-low condition, but do not block USB commands.
    while (readRxPin() == HIGH) {
      if (handleSerialCommands()) return -2;
      yield();
    }

    // TX idles LOW, so the receiver can sit here for a long time between
    // transmissions. Keep polling commands so GUI FREQ changes still work.
    while (readRxPin() == LOW) {
      if (handleSerialCommands()) return -2;
      yield();
    }

    // We saw the low-to-high transition of the start bit. Sample in the
    // middle of the next half-bit before reading data bits.
    delayMicroseconds(halfBitUs / 2);

    uint8_t value = 0;
    bool valid = true;
    for (int i = 7; i >= 0; i--) {
      delayMicroseconds(halfBitUs);
      bool first = readRxPin();
      delayMicroseconds(halfBitUs);
      bool second = readRxPin();

      if (first == second) {
        valid = false;
        break;
      }

      bool bit = second;
      if (bit) {
        value |= (1 << i);
      }
    }

    if (!valid) {
      if (rxDebug) {
        Serial.println("RX_ERROR: unstable Manchester bit, resyncing");
      }
      continue;
    }

    return value;
  }
}

uint16_t crc16_ccitt(uint16_t crc, uint8_t data) {
  crc ^= (uint16_t)data << 8;
  for (uint8_t i = 0; i < 8; i++) {
    if (crc & 0x8000) {
      crc = (crc << 1) ^ 0x1021;
    } else {
      crc <<= 1;
    }
  }
  return crc & 0xFFFF;
}

void resetFrame() {
  rxState = WAIT_START;
  frameType = 0;
  expectedSize = 0;
  bytesRemaining = 0;
  expectedCRC = 0;
  computedCRC = 0;
  if (payloadBuffer != nullptr) {
    free(payloadBuffer);
    payloadBuffer = nullptr;
  }
}

void processReceivedByte(uint8_t data) {
  switch (rxState) {
    case WAIT_START:
      if (data == 0x02) {
        rxState = READ_TYPE;
      } else {
        // Framed-only receiver: ignore all non-start bytes.
        if (rxDebug && data != 0xAA) {
          Serial.print("RX_DISCARD: 0x");
          if (data < 0x10) Serial.print('0');
          Serial.println(data, HEX);
        }
      }
      break;

    case READ_TYPE:
      frameType = data;
      if (frameType == 0x00 || frameType == 0x01 || frameType == 0x02) {
        rxState = READ_SIZE_MSB;
      } else {
        resetFrame();
      }
      break;

    case READ_SIZE_MSB:
      expectedSize = ((uint16_t)data) << 8;
      rxState = READ_SIZE_LSB;
      break;

    case READ_SIZE_LSB:
      expectedSize |= data;
      bytesRemaining = expectedSize;
      computedCRC = 0xFFFF;

      if (payloadBuffer != nullptr) {
        free(payloadBuffer);
        payloadBuffer = nullptr;
      }

      if (expectedSize == 0) {
        Serial.println("RX_LOG: empty transfer received");
        resetFrame();
        break;
      }

      payloadBuffer = (uint8_t *)malloc(expectedSize);
      if (payloadBuffer == nullptr) {
        Serial.println("RX_ERROR: cannot allocate payload buffer");
        resetFrame();
        break;
      }

      if (frameType == 0x00) {
        // No-CRC file frame: START, TYPE, SIZE, PAYLOAD
        rxState = READ_DATA;
      } else {
        // CRC frame: START, TYPE, SIZE, CRC, PAYLOAD
        rxState = READ_CRC_MSB;
      }
      break;

    case READ_CRC_MSB:
      expectedCRC = ((uint16_t)data) << 8;
      rxState = READ_CRC_LSB;
      break;

    case READ_CRC_LSB:
      expectedCRC |= data;
      rxState = READ_DATA;
      break;

    case READ_DATA: {
      computedCRC = crc16_ccitt(computedCRC, data);

      uint16_t index = expectedSize - bytesRemaining;
      if (payloadBuffer != nullptr && index < expectedSize) {
        payloadBuffer[index] = data;
      }

      if (bytesRemaining > 0) {
        bytesRemaining--;
      }

      uint16_t bytesReceived = expectedSize - bytesRemaining;
      if (bytesReceived % 128 == 0 || bytesRemaining == 0) {
        if (frameType == 0x02) {
          Serial.print("RX_TEXT_PROGRESS: ");
        } else {
          Serial.print("RX_FILE_PROGRESS: ");
        }
        Serial.print(bytesReceived);
        Serial.print("/");
        Serial.println(expectedSize);
      }

      if (bytesRemaining == 0) {
        bool frameOk = (frameType == 0x00) || (computedCRC == expectedCRC);

        if (frameOk) {
          if (frameType == 0x02) {
            Serial.print("RX_TEXT_START:");
            Serial.println(expectedSize);
            Serial.write(payloadBuffer, expectedSize);
            Serial.println();       // delimiter after exact-length text payload
            Serial.println("RX_TEXT_CRC_OK");
            Serial.println("RX_TEXT_COMPLETE");
          } else {
            Serial.print("RX_FILE_START:");
            Serial.println(expectedSize);
            Serial.write(payloadBuffer, expectedSize);
            Serial.println();       // delimiter after exact-length file payload
            if (frameType == 0x01) {
              Serial.println("RX_FILE_CRC_OK");
            } else {
              Serial.println("RX_FILE_NO_CRC");
            }
            Serial.println("RX_FILE_COMPLETE");
          }
        } else {
          if (frameType == 0x02) {
            Serial.print("RX_TEXT_CRC_FAIL:");
          } else {
            Serial.print("RX_FILE_CRC_FAIL:");
          }
          Serial.print(computedCRC, HEX);
          Serial.print(" expected=");
          Serial.println(expectedCRC, HEX);
          if (frameType != 0x02) {
            Serial.println("RX_FILE_COMPLETE");
          }
        }
        resetFrame();
      }
      break;
    }
  }
}

void setFrequency(uint32_t f) {
  if (f < 1) {
    Serial.println("RX: FREQ too low, using 1 Hz");
    f = 1;
  } else if (f > MAX_FREQUENCY_HZ) {
    Serial.print("RX: FREQ too high, using ");
    Serial.print(MAX_FREQUENCY_HZ);
    Serial.println(" Hz");
    f = MAX_FREQUENCY_HZ;
  }

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);
  if (halfBitUs < 1) halfBitUs = 1;

  Serial.print("RX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}
