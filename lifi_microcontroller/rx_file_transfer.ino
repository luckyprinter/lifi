// RX - ESP32 Manchester File Transfer Receiver (FIXED)
// Fixes CRC order mismatch: GUI/TX sends CRC BEFORE payload.
// Also fixes file transfer flow: payload is written to GUI only after CRC OK.

#define RX_PIN 5

uint32_t frequencyHz = 500;
uint32_t halfBitUs;

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
uint8_t *filePayloadBuffer = nullptr;
bool rxDebug = false;
String plainTextBuffer = "";
String textChunkBuffer = "";

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);

  setFrequency(frequencyHz);
  Serial.println("RX File Transfer Ready");
}

void loop() {
  // NOTE: receiveManchesterByte() blocks while waiting for optical edges.
  // Send FREQ/DEBUG commands before starting a transfer.
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("FREQ=")) {
      setFrequency(cmd.substring(5).toInt());
      return;
    }
    if (cmd.startsWith("DEBUG=")) {
      rxDebug = (cmd.substring(6).toInt() != 0);
      Serial.print("RX debug ");
      Serial.println(rxDebug ? "enabled" : "disabled");
      return;
    }
  }

  int received = receiveManchesterByte();
  if (received < 0) {
    return;
  }

  uint8_t data = (uint8_t)received;
  processReceivedByte(data);
}

int receiveManchesterByte() {
  while (true) {
    while (digitalRead(RX_PIN) == HIGH) {
      // wait for start low
    }
    while (digitalRead(RX_PIN) == LOW) {
      // wait for transition high
    }

    delayMicroseconds(halfBitUs / 2);

    uint8_t value = 0;
    bool valid = true;
    for (int i = 7; i >= 0; i--) {
      delayMicroseconds(halfBitUs);
      bool first = digitalRead(RX_PIN);
      delayMicroseconds(halfBitUs);
      bool second = digitalRead(RX_PIN);

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
  textChunkBuffer = "";
  if (filePayloadBuffer != nullptr) {
    free(filePayloadBuffer);
    filePayloadBuffer = nullptr;
  }
}

void processReceivedByte(uint8_t data) {
  switch (rxState) {
    case WAIT_START:
      if (data == 0x02) {
        rxState = READ_TYPE;
      } else if (data == 0xAA) {
        // preamble while waiting for frame start
      } else {
        // Optional plain text fallback for non-framed bytes
        if (data == '\n') {
          Serial.println(plainTextBuffer);
          plainTextBuffer = "";
        } else if (data != '\r') {
          plainTextBuffer += (char)data;
        }
      }
      break;

    case READ_TYPE:
      frameType = data;
      if (frameType == 0x01 || frameType == 0x02) {
        // 0x01 = binary file transfer with CRC
        // 0x02 = text chunk with CRC
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
      textChunkBuffer = "";

      if (filePayloadBuffer != nullptr) {
        free(filePayloadBuffer);
        filePayloadBuffer = nullptr;
      }

      if (expectedSize == 0) {
        Serial.println("RX_LOG: empty transfer received");
        resetFrame();
        break;
      }

      // IMPORTANT FIX:
      // GUI/TX frame order is: START, TYPE, SIZE, CRC, PAYLOAD
      // so the receiver must read CRC first, then payload.
      rxState = READ_CRC_MSB;
      break;

    case READ_CRC_MSB:
      expectedCRC = ((uint16_t)data) << 8;
      rxState = READ_CRC_LSB;
      break;

    case READ_CRC_LSB:
      expectedCRC |= data;

      if (frameType == 0x01) {
        filePayloadBuffer = (uint8_t *)malloc(expectedSize);
        if (filePayloadBuffer == nullptr) {
          Serial.println("RX_ERROR: cannot allocate file buffer");
          resetFrame();
          break;
        }
      }

      rxState = READ_DATA;
      break;

    case READ_DATA:
      computedCRC = crc16_ccitt(computedCRC, data);

      if (frameType == 0x01) {
        uint16_t index = expectedSize - bytesRemaining;
        if (filePayloadBuffer != nullptr && index < expectedSize) {
          filePayloadBuffer[index] = data;
        }
      } else if (frameType == 0x02) {
        textChunkBuffer += (char)data;
      }

      if (bytesRemaining > 0) {
        bytesRemaining--;
      }

      if (frameType == 0x01) {
        uint16_t bytesReceived = expectedSize - bytesRemaining;
        if (bytesReceived % 128 == 0 || bytesRemaining == 0) {
          Serial.print("RX_FILE_PROGRESS: ");
          Serial.print(bytesReceived);
          Serial.print("/");
          Serial.println(expectedSize);
        }
      }

      if (bytesRemaining == 0) {
        if (computedCRC == expectedCRC) {
          if (frameType == 0x02) {
            plainTextBuffer += textChunkBuffer;
            textChunkBuffer = "";
            int newlineIndex;
            while ((newlineIndex = plainTextBuffer.indexOf('\n')) >= 0) {
              String line = plainTextBuffer.substring(0, newlineIndex);
              if (line.endsWith("\r")) {
                line.remove(line.length() - 1);
              }
              Serial.print("RX: ");
              Serial.println(line);
              plainTextBuffer = plainTextBuffer.substring(newlineIndex + 1);
            }
          } else {
            // Only now tell the GUI to expect raw file bytes.
            Serial.print("RX_FILE_START:");
            Serial.println(expectedSize);
            if (filePayloadBuffer != nullptr) {
              Serial.write(filePayloadBuffer, expectedSize);
            }
            Serial.println();
            Serial.println("RX_FILE_CRC_OK");
            Serial.println("RX_FILE_COMPLETE");
          }
        } else {
          if (frameType == 0x02) {
            Serial.print("RX_TEXT_CRC_FAIL:");
            Serial.print(computedCRC, HEX);
            Serial.print(" expected=");
            Serial.println(expectedCRC, HEX);
          } else {
            Serial.print("RX_FILE_CRC_FAIL:");
            Serial.print(computedCRC, HEX);
            Serial.print(" expected=");
            Serial.println(expectedCRC, HEX);
            Serial.println("RX_FILE_COMPLETE");
          }
        }
        resetFrame();
      }
      break;
  }
}

void setFrequency(uint32_t f) {
  if (f < 1) {
    Serial.println("RX: FREQ too low, using 1 Hz");
    f = 1;
  } else if (f > 1000) {
    Serial.println("RX: FREQ too high, using 1000 Hz");
    f = 1000;
  }

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("RX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}
