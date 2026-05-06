// TX - Arduino UNO Manchester File Transfer
// Compatible with raw binary file transfer over serial-to-light using stable Manchester timing.

#define TX_PIN 8
const uint8_t PREAMBLE_BYTE = 0xAA;
const uint8_t FILE_TRANSFER_TYPE = 0x01;
const uint8_t PREAMBLE_COUNT = 4;

uint32_t frequencyHz = 500;
uint32_t halfBitUs;

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);

  setFrequency(frequencyHz);
  Serial.println("TX File Transfer Ready");
}

void loop() {
  if (!Serial.available()) {
    return;
  }

  int peeked = Serial.peek();
  if (peeked == 'F') {
    handleCommand();
    return;
  }

  if (peeked == 0x02) {
    if (Serial.available() < 2) {
      return;
    }

    Serial.read(); // consume START byte
    int type = Serial.peek();
    if (type == FILE_TRANSFER_TYPE) {
      if (Serial.available() < 6) {
        return; // wait for full CRC header
      }
      Serial.read(); // consume type
      uint16_t size = (uint16_t)Serial.read() << 8;
      size |= (uint16_t)Serial.read();
      uint16_t crc = (uint16_t)Serial.read() << 8;
      crc |= (uint16_t)Serial.read();

      sendManchesterPreamble(PREAMBLE_COUNT);
      sendManchesterByte(0x02);
      sendManchesterByte((uint8_t)FILE_TRANSFER_TYPE);
      sendManchesterByte((size >> 8) & 0xFF);
      sendManchesterByte(size & 0xFF);
      sendManchesterByte((crc >> 8) & 0xFF);
      sendManchesterByte(crc & 0xFF);

      for (uint16_t remaining = size; remaining > 0; remaining--) {
        while (!Serial.available()) {
        }
        sendManchesterByte((uint8_t)Serial.read());
      }

      Serial.println("TX: file stream sent (CRC)");
      return;
    }

    if (type == 0x00) {
      if (Serial.available() < 4) {
        return; // wait for full no-CRC header
      }
      Serial.read(); // consume type
      uint16_t size = (uint16_t)Serial.read() << 8;
      size |= (uint16_t)Serial.read();

      sendManchesterPreamble(PREAMBLE_COUNT);
      sendManchesterByte(0x02);
      sendManchesterByte(0x00);
      sendManchesterByte((size >> 8) & 0xFF);
      sendManchesterByte(size & 0xFF);

      for (uint16_t remaining = size; remaining > 0; remaining--) {
        while (!Serial.available()) {
        }
        sendManchesterByte((uint8_t)Serial.read());
      }

      Serial.println("TX: file stream sent (no CRC)");
      return;
    }

    // Not a file frame, treat as normal byte sequence
    sendManchesterByte(0x02);
    return;
  }

  // Normal byte-by-byte Manchester transmission
  uint8_t b = (uint8_t)Serial.read();
  sendManchesterByte(b);
}

void handleCommand() {
  String line = Serial.readStringUntil('\n');
  line.trim();

  if (line.startsWith("FREQ=")) {
    uint32_t newFreq = line.substring(5).toInt();
    setFrequency(newFreq);
    return;
  }

  Serial.print("TX: unknown command ");
  Serial.println(line);
}

void sendManchesterPreamble(uint8_t count) {
  for (uint8_t i = 0; i < count; i++) {
    sendManchesterByte(PREAMBLE_BYTE);
  }
}

void setFrequency(uint32_t f) {
  if (f == 0) {
    return;
  }

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("TX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}

void sendManchesterByte(uint8_t b) {
  digitalWrite(TX_PIN, LOW);
  delayMicroseconds(halfBitUs);
  digitalWrite(TX_PIN, HIGH);
  delayMicroseconds(halfBitUs);

  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 0x01;
    digitalWrite(TX_PIN, !bit);
    delayMicroseconds(halfBitUs);
    digitalWrite(TX_PIN, bit);
    delayMicroseconds(halfBitUs);
  }

  digitalWrite(TX_PIN, HIGH);
  delayMicroseconds(halfBitUs);
  digitalWrite(TX_PIN, LOW);
  delayMicroseconds(halfBitUs);
}
