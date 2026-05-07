// ESP32 TX - Manchester File Transfer, buffered + ACK/status friendly
// 50 kHz experimental range version
// Fixes long text/file loss by reading the whole serial payload first,
// then transmitting optically. The GUI can wait for TX done markers per frame.

#include "driver/gpio.h"

#define TX_PIN 5

inline void setTxPin(bool level) {
#if defined(ARDUINO_ARCH_ESP32)
  gpio_set_level((gpio_num_t)TX_PIN, level ? 1 : 0);
#else
  digitalWrite(TX_PIN, level ? HIGH : LOW);
#endif
}

const uint8_t PREAMBLE_BYTE = 0xAA;
const uint8_t FILE_TRANSFER_TYPE = 0x01;
const uint8_t TEXT_TRANSFER_TYPE = 0x02;
const uint8_t NOCRC_FILE_TYPE = 0x00;
const uint8_t PREAMBLE_COUNT_FILE = 4;
const uint8_t PREAMBLE_COUNT_TEXT = 16;

uint32_t frequencyHz = 500;
uint32_t halfBitUs = 1000;
const uint32_t MAX_FREQUENCY_HZ = 50000;

void setup() {
#if defined(ARDUINO_ARCH_ESP32)
  Serial.setRxBufferSize(8192);
#endif
  Serial.begin(115200);
  Serial.setTimeout(25);
  pinMode(TX_PIN, OUTPUT);
  setTxPin(LOW);

  setFrequency(frequencyHz);
  Serial.println("ESP32 TX File Transfer Ready - 50 kHz experimental command-fix");
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

  if (peeked != 0x02) {
    // Fallback: transmit ordinary serial bytes one by one.
    uint8_t b = (uint8_t)Serial.read();
    sendManchesterByte(b);
    delayMicroseconds(200);
    return;
  }

  // Framed mode from GUI: START, TYPE, SIZE, [CRC], PAYLOAD
  Serial.read(); // consume START byte 0x02

  int typeRead = readByteWithTimeout(1000);
  if (typeRead < 0) {
    Serial.println("TX_ERROR: timeout reading frame type");
    return;
  }
  uint8_t type = (uint8_t)typeRead;

  int msb = readByteWithTimeout(1000);
  int lsb = readByteWithTimeout(1000);
  if (msb < 0 || lsb < 0) {
    Serial.println("TX_ERROR: timeout reading size");
    return;
  }
  uint16_t size = ((uint16_t)msb << 8) | (uint16_t)lsb;

  uint16_t crc = 0;
  bool hasCRC = (type == FILE_TRANSFER_TYPE || type == TEXT_TRANSFER_TYPE);
  if (hasCRC) {
    int crcMsb = readByteWithTimeout(1000);
    int crcLsb = readByteWithTimeout(1000);
    if (crcMsb < 0 || crcLsb < 0) {
      Serial.println("TX_ERROR: timeout reading CRC");
      return;
    }
    crc = ((uint16_t)crcMsb << 8) | (uint16_t)crcLsb;
  } else if (type != NOCRC_FILE_TYPE) {
    Serial.print("TX_ERROR: unknown frame type 0x");
    Serial.println(type, HEX);
    return;
  }

  uint8_t *payload = nullptr;
  if (size > 0) {
    payload = (uint8_t *)malloc(size);
    if (payload == nullptr) {
      Serial.println("TX_ERROR: cannot allocate payload buffer");
      return;
    }

    // Read the serial payload quickly first. Do not transmit optically while reading,
    // otherwise the USB serial buffer can overflow during long/slow optical sends.
    if (!readExact(payload, size, 15000)) {
      Serial.println("TX_ERROR: timeout reading payload from GUI");
      free(payload);
      return;
    }
  }

  if (type == TEXT_TRANSFER_TYPE) {
    sendManchesterPreamble(PREAMBLE_COUNT_TEXT);
  } else {
    sendManchesterPreamble(PREAMBLE_COUNT_FILE);
  }

  sendManchesterByte(0x02);
  sendManchesterByte(type);
  sendManchesterByte((size >> 8) & 0xFF);
  sendManchesterByte(size & 0xFF);

  if (hasCRC) {
    sendManchesterByte((crc >> 8) & 0xFF);
    sendManchesterByte(crc & 0xFF);
  }

  for (uint16_t i = 0; i < size; i++) {
    sendManchesterByte(payload[i]);
    if ((i + 1) % 128 == 0 || i + 1 == size) {
      Serial.print("TX_FILE_PROGRESS: ");
      Serial.print(i + 1);
      Serial.print("/");
      Serial.println(size);
    }
    delayMicroseconds(halfBitUs);
  }

  if (payload != nullptr) {
    free(payload);
  }

  if (type == FILE_TRANSFER_TYPE) {
    Serial.println("TX: file stream sent (CRC)");
  } else if (type == TEXT_TRANSFER_TYPE) {
    Serial.print("TX: text frame sent (");
    Serial.print(size);
    Serial.println(" bytes)");
  } else {
    Serial.println("TX: file stream sent (no CRC)");
  }
}

int readByteWithTimeout(uint32_t timeoutMs) {
  uint32_t start = millis();
  while (!Serial.available()) {
    if (millis() - start > timeoutMs) {
      return -1;
    }
    delay(1);
  }
  return Serial.read();
}

bool readExact(uint8_t *buffer, uint16_t len, uint32_t timeoutMs) {
  uint16_t received = 0;
  uint32_t lastByteTime = millis();

  while (received < len) {
    while (Serial.available() && received < len) {
      buffer[received++] = (uint8_t)Serial.read();
      lastByteTime = millis();
    }
    if (millis() - lastByteTime > timeoutMs) {
      return false;
    }
    delay(1);
  }
  return true;
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
  if (f < 1) {
    Serial.println("TX: FREQ too low, using 1 Hz");
    f = 1;
  } else if (f > MAX_FREQUENCY_HZ) {
    Serial.print("TX: FREQ too high, using ");
    Serial.print(MAX_FREQUENCY_HZ);
    Serial.println(" Hz");
    f = MAX_FREQUENCY_HZ;
  }

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);
  if (halfBitUs < 1) halfBitUs = 1;

  Serial.print("TX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}

void sendManchesterByte(uint8_t b) {
  setTxPin(LOW);
  delayMicroseconds(halfBitUs);
  setTxPin(HIGH);
  delayMicroseconds(halfBitUs);

  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 0x01;
    setTxPin(!bit);
    delayMicroseconds(halfBitUs);
    setTxPin(bit);
    delayMicroseconds(halfBitUs);
  }

  setTxPin(HIGH);
  delayMicroseconds(halfBitUs);
  setTxPin(LOW);
  delayMicroseconds(halfBitUs);
}
