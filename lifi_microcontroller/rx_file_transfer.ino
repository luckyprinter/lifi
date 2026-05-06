// RX - ESP32 Manchester File Transfer Receiver
// Reconstructs raw binary stream from Manchester-encoded optical link.

#define RX_PIN 5

uint32_t frequencyHz = 500;
uint32_t halfBitUs;

enum RxState {
  WAIT_START,
  READ_TYPE,
  READ_SIZE_MSB,
  READ_SIZE_LSB,
  READ_DATA,
  READ_CRC_MSB,
  READ_CRC_LSB
};

RxState rxState = WAIT_START;
uint8_t frameType = 0;
uint16_t expectedSize = 0;
uint16_t bytesRemaining = 0;
uint16_t expectedCRC = 0;
uint16_t computedCRC = 0;
bool rxDebug = false;

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);

  setFrequency(frequencyHz);
  Serial.println("RX File Transfer Ready");
}

void loop() {
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
  while (digitalRead(RX_PIN) == HIGH);
  while (digitalRead(RX_PIN) == LOW);

  delayMicroseconds(halfBitUs / 2);

  uint8_t value = 0;
  for (int i = 7; i >= 0; i--) {
    delayMicroseconds(halfBitUs);
    bool first = digitalRead(RX_PIN);
    delayMicroseconds(halfBitUs);
    bool second = digitalRead(RX_PIN);

    if (first == second) {
      if (rxDebug) {
        Serial.println("RX_ERROR: unstable Manchester bit");
      }
      return -1;
    }

    bool bit = second;
    if (bit) {
      value |= (1 << i);
    }
  }

  return value;
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

void processReceivedByte(uint8_t data) {
  switch (rxState) {
    case WAIT_START:
      if (data == 0x02) {
        rxState = READ_TYPE;
      } else if (data == 0xAA) {
        // preamble while waiting for frame start
      } else {
        Serial.write(data);
      }
      break;

    case READ_TYPE:
      frameType = data;
      if (frameType == 0x01) {
        rxState = READ_SIZE_MSB;
      } else {
        rxState = WAIT_START;
      }
      break;

    case READ_SIZE_MSB:
      expectedSize = ((uint16_t)data) << 8;
      rxState = READ_SIZE_LSB;
      break;

    case READ_SIZE_LSB:
      expectedSize |= data;
      bytesRemaining = expectedSize;
      computedCRC = 0;
      if (expectedSize == 0) {
        Serial.println("RX_LOG: empty transfer received");
        rxState = WAIT_START;
      } else {
        Serial.print("RX_FILE_START:");
        Serial.print(expectedSize);
        Serial.println();
        rxState = READ_DATA;
      }
      break;

    case READ_DATA:
      Serial.write(data);
      if (frameType == 0x01) {
        computedCRC = crc16_ccitt(computedCRC, data);
      }
      if (bytesRemaining > 0) {
        bytesRemaining--;
      }
      if (bytesRemaining == 0) {
        if (frameType == 0x01) {
          rxState = READ_CRC_MSB;
        } else {
          Serial.println();
          Serial.println("RX_FILE_COMPLETE");
          rxState = WAIT_START;
        }
      }
      break;

    case READ_CRC_MSB:
      expectedCRC = ((uint16_t)data) << 8;
      rxState = READ_CRC_LSB;
      break;

    case READ_CRC_LSB:
      expectedCRC |= data;
      if (computedCRC == expectedCRC) {
        Serial.println();
        Serial.println("RX_FILE_CRC_OK");
        Serial.println("RX_FILE_COMPLETE");
      } else {
        Serial.println();
        Serial.print("RX_FILE_CRC_FAIL:");
        Serial.print(computedCRC, HEX);
        Serial.print(" expected=");
        Serial.println(expectedCRC, HEX);
        Serial.println("RX_FILE_COMPLETE");
      }
      rxState = WAIT_START;
      break;
  }
}

void setFrequency(uint32_t f) {
  if (f == 0) {
    return;
  }

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("RX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}
