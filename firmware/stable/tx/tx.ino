#include "driver/gpio.h"

#define TX_PIN 5

const uint8_t START_BYTE = 0x02;
const uint8_t PREAMBLE_BYTE = 0xAA;
const uint8_t TYPE_CAROUSEL_CHUNK = 0x20;
const uint8_t TYPE_CAROUSEL_PARITY = 0x21;

const uint8_t PREAMBLE_COUNT = 32;
const uint32_t MAX_FREQUENCY_HZ = 50000;

uint32_t frequencyHz = 9000;
uint32_t halfBitUs = 55;

// Your hardware is active-low:
// ESP32 LOW  = LED ON
// ESP32 HIGH = LED OFF
inline void txLightOn() {
  gpio_set_level((gpio_num_t)TX_PIN, 0);
}

inline void txLightOff() {
  gpio_set_level((gpio_num_t)TX_PIN, 1);
}

void setup() {
#if defined(ARDUINO_ARCH_ESP32)
  Serial.setRxBufferSize(8192);
#endif

  Serial.begin(115200);
  Serial.setTimeout(25);

  pinMode(TX_PIN, OUTPUT);

  txLightOn();

  setFrequency(frequencyHz);

  Serial.println("ESP32 TX Ready - carousel active-low idle ON");
}

void loop() {
  if (!Serial.available()) return;

  int peeked = Serial.peek();

  if (peeked == 'F') {
    handleCommand();
    return;
  }

  if (peeked != START_BYTE) {
    Serial.read();
    return;
  }

  Serial.read();

  int typeRead = readByteWithTimeout(1000);
  if (typeRead < 0) {
    Serial.println("TX_ERROR: timeout reading frame type");
    return;
  }

  uint8_t frameType = (uint8_t)typeRead;

  int msb = readByteWithTimeout(1000);
  int lsb = readByteWithTimeout(1000);

  if (msb < 0 || lsb < 0) {
    Serial.println("TX_ERROR: timeout reading size");
    return;
  }

  uint16_t size = ((uint16_t)msb << 8) | (uint16_t)lsb;

  int crcMsb = readByteWithTimeout(1000);
  int crcLsb = readByteWithTimeout(1000);

  if (crcMsb < 0 || crcLsb < 0) {
    Serial.println("TX_ERROR: timeout reading CRC");
    return;
  }

  uint16_t frameCRC = ((uint16_t)crcMsb << 8) | (uint16_t)crcLsb;

  if (frameType != TYPE_CAROUSEL_CHUNK && frameType != TYPE_CAROUSEL_PARITY) {
    Serial.print("TX_ERROR: unknown frame type 0x");
    Serial.println(frameType, HEX);
    discardBytes(size);
    return;
  }

  uint8_t *payload = nullptr;

  if (size > 0) {
    payload = (uint8_t *)malloc(size);

    if (!payload) {
      Serial.println("TX_ERROR: cannot allocate payload buffer");
      discardBytes(size);
      return;
    }

    if (!readExact(payload, size, 15000)) {
      Serial.println("TX_ERROR: timeout reading payload from GUI");
      free(payload);
      return;
    }
  }

  sendFrameGap();
  uint32_t txDeadline = micros();

  sendManchesterPreamble(PREAMBLE_COUNT, txDeadline);

  sendManchesterByte(START_BYTE, txDeadline);
  sendManchesterByte(frameType, txDeadline);
  sendManchesterByte((size >> 8) & 0xFF, txDeadline);
  sendManchesterByte(size & 0xFF, txDeadline);
  sendManchesterByte((frameCRC >> 8) & 0xFF, txDeadline);
  sendManchesterByte(frameCRC & 0xFF, txDeadline);

  for (uint16_t i = 0; i < size; i++) {
    sendManchesterByte(payload[i], txDeadline);
  }

  txLightOn();

  if (payload) free(payload);

  Serial.print("TX_CAROUSEL_FRAME_SENT: ");
  Serial.print(size);
  Serial.println(" bytes payload");
}

int readByteWithTimeout(uint32_t timeoutMs) {
  uint32_t start = millis();

  while (!Serial.available()) {
    if (millis() - start > timeoutMs) return -1;
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

    if (millis() - lastByteTime > timeoutMs) return false;

    delay(1);
  }

  return true;
}

void discardBytes(uint16_t n) {
  uint32_t start = millis();
  uint16_t discarded = 0;

  while (discarded < n && millis() - start < 2000) {
    if (Serial.available()) {
      Serial.read();
      discarded++;
    } else {
      delay(1);
    }
  }
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

void sendFrameGap() {
  txLightOn();

  uint32_t gapUs = halfBitUs * 80;

  if (gapUs < 2000) gapUs = 2000;
  if (gapUs > 12000) gapUs = 12000;

  delayMicroseconds(gapUs);
}

void sendManchesterPreamble(uint8_t count, uint32_t &deadline) {
  for (uint8_t i = 0; i < count; i++) {
    sendManchesterByte(PREAMBLE_BYTE, deadline);
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

void waitUntilMicros(uint32_t deadline) {
  while ((int32_t)(micros() - deadline) < 0) {
    ;
  }
}

void waitNextHalfBit(uint32_t &deadline) {
  deadline += halfBitUs;
  waitUntilMicros(deadline);
}

void sendManchesterByte(uint8_t b, uint32_t &deadline) {
  txLightOff();
  waitNextHalfBit(deadline);
  txLightOn();
  waitNextHalfBit(deadline);

  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 0x01;

    if (bit) {
      txLightOn();
      waitNextHalfBit(deadline);
      txLightOff();
      waitNextHalfBit(deadline);
    } else {
      txLightOff();
      waitNextHalfBit(deadline);
      txLightOn();
      waitNextHalfBit(deadline);
    }
  }

  txLightOn();
  waitNextHalfBit(deadline);
}
