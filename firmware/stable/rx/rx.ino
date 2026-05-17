#include "driver/gpio.h"

#define RX_PIN 5

const uint8_t START_BYTE = 0x02;
const uint8_t PREAMBLE_BYTE = 0xAA;
const uint8_t TYPE_CAROUSEL_CHUNK = 0x20;
const uint8_t TYPE_CAROUSEL_PARITY = 0x21;

const uint32_t MAX_FREQUENCY_HZ = 50000;
const uint8_t MIN_PREAMBLE_COUNT = 8;
const uint16_t CAROUSEL_HEADER_MIN = 16;
const uint16_t PARITY_HEADER_MIN = 19;

// Keep the Manchester decoder on the raw GPIO polarity used by the earlier
// working receiver. With the TEPT4400 divider, light ON is a lower voltage and
// light OFF is a higher voltage. That raw inverted waveform is already what
// the working Manchester bit mapping expects, so do not normalize it here.
const bool RX_LIGHT_ACTIVE_LOW = false;

uint32_t frequencyHz = 1000;
uint32_t halfBitUs = 500;
bool rxDebug = false;
bool rxDiagnostics = false;

uint32_t decodedBytes = 0;
uint32_t unstableBits = 0;
uint32_t framesOk = 0;
uint32_t badCrcFrames = 0;
uint32_t badHeaderFrames = 0;

inline int readRxRawPin() {
  return gpio_get_level((gpio_num_t)RX_PIN);
}

inline int readRxPin() {
  int raw = readRxRawPin();
  return RX_LIGHT_ACTIVE_LOW ? !raw : raw;
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

uint8_t preambleSeen = 0;
uint8_t frameType = 0;

uint16_t expectedSize = 0;
uint16_t bytesRemaining = 0;
uint16_t expectedCRC = 0;
uint16_t computedCRC = 0;

uint8_t *payloadBuffer = nullptr;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);

  pinMode(RX_PIN, INPUT);

  setFrequency(frequencyHz);

  Serial.println("ESP32 RX Ready - one-way carousel protocol");
}

void loop() {
  handleSerialCommands();

  int received = receiveManchesterByte();

  if (received < 0) return;

  processReceivedByte((uint8_t)received);
}

bool handleSerialCommands() {
  bool handled = false;

  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.length() == 0) continue;

    if (cmd.startsWith("FREQ=")) {
      setFrequency(cmd.substring(5).toInt());
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

    if (cmd.startsWith("RXDIAG=") || cmd.startsWith("DIAG=")) {
      int equals = cmd.indexOf('=');
      rxDiagnostics = (cmd.substring(equals + 1).toInt() != 0);
      Serial.print("RX diagnostics ");
      Serial.println(rxDiagnostics ? "enabled" : "disabled");
      printRxStats();
      handled = true;
      continue;
    }

    if (cmd.startsWith("STATS")) {
      printRxStats();
      handled = true;
      continue;
    }

    if (cmd.startsWith("RXTEST")) {
      runRxInputTest();
      resetFrame();
      handled = true;
      continue;
    }

    Serial.print("RX: unknown command ");
    Serial.println(cmd);
    handled = true;
  }

  return handled;
}

void runRxInputTest() {
  const uint32_t durationMs = 1200;
  const uint32_t sampleGapUs = 200;
  uint32_t startMs = millis();
  uint32_t samples = 0;
  uint32_t rawHighCount = 0;
  uint32_t rawLowCount = 0;
  uint32_t lightHighCount = 0;
  uint32_t lightLowCount = 0;
  uint32_t transitions = 0;
  int last = readRxRawPin();

  Serial.println("RX_INPUT_TEST_START");

  while (millis() - startMs < durationMs) {
    int current = readRxRawPin();
    int light = RX_LIGHT_ACTIVE_LOW ? !current : current;

    if (current == HIGH) rawHighCount++;
    else rawLowCount++;

    if (light == HIGH) lightHighCount++;
    else lightLowCount++;

    if (current != last) {
      transitions++;
      last = current;
    }

    samples++;
    delayMicroseconds(sampleGapUs);
  }

  Serial.print("RX_INPUT_TEST_DONE:samples=");
  Serial.print(samples);
  Serial.print(":rawHigh=");
  Serial.print(rawHighCount);
  Serial.print(":rawLow=");
  Serial.print(rawLowCount);
  Serial.print(":lightHigh=");
  Serial.print(lightHighCount);
  Serial.print(":lightLow=");
  Serial.print(lightLowCount);
  Serial.print(":transitions=");
  Serial.print(transitions);
  Serial.print(":activeLow=");
  Serial.println(RX_LIGHT_ACTIVE_LOW ? 1 : 0);
}

void printRxStats() {
  Serial.print("RX_STATS:freq=");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.print(halfBitUs);
  Serial.print(":pin=");
  Serial.print(RX_PIN);
  Serial.print(":lightActiveLow=");
  Serial.print(RX_LIGHT_ACTIVE_LOW ? 1 : 0);
  Serial.print(":debug=");
  Serial.print(rxDebug ? 1 : 0);
  Serial.print(":diag=");
  Serial.print(rxDiagnostics ? 1 : 0);
  Serial.print(":decodedBytes=");
  Serial.print(decodedBytes);
  Serial.print(":framesOk=");
  Serial.print(framesOk);
  Serial.print(":badCrc=");
  Serial.print(badCrcFrames);
  Serial.print(":badHeader=");
  Serial.print(badHeaderFrames);
  Serial.print(":unstableBits=");
  Serial.println(unstableBits);
}

int receiveManchesterByte() {
  while (true) {
    while (readRxPin() == HIGH) {
      if (handleSerialCommands()) return -2;
      yield();
    }

    while (readRxPin() == LOW) {
      if (handleSerialCommands()) return -2;
      yield();
    }

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

      if (bit) value |= (1 << i);
    }

    if (!valid) {
      unstableBits++;
      if (rxDebug && (unstableBits <= 10 || unstableBits % 25 == 0)) {
        Serial.print("RX_ERROR: unstable Manchester bit count=");
        Serial.println(unstableBits);
      }
      continue;
    }

    decodedBytes++;
    return value;
  }
}

void waitUntilMicros(uint32_t deadline) {
  while ((int32_t)(micros() - deadline) < 0) {
    ;
  }
}

bool majorityRead() {
  uint8_t ones = 0;
  uint32_t spreadUs = halfBitUs / 12;

  if (spreadUs < 1) spreadUs = 1;
  if (spreadUs > 3) spreadUs = 3;

  if (readRxPin()) ones++;
  delayMicroseconds(spreadUs);
  if (readRxPin()) ones++;
  delayMicroseconds(spreadUs);
  if (readRxPin()) ones++;

  return ones >= 2;
}

uint16_t crc16_ccitt(uint16_t crc, uint8_t data) {
  crc ^= (uint16_t)data << 8;

  for (uint8_t i = 0; i < 8; i++) {
    if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
    else crc <<= 1;
  }

  return crc & 0xFFFF;
}

void resetFrame() {
  rxState = WAIT_START;
  preambleSeen = 0;
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

uint16_t readU16BE(uint8_t *p) {
  return ((uint16_t)p[0] << 8) | p[1];
}

uint32_t readU32BE(uint8_t *p) {
  return ((uint32_t)p[0] << 24) |
         ((uint32_t)p[1] << 16) |
         ((uint32_t)p[2] << 8) |
         p[3];
}

void processReceivedByte(uint8_t data) {
  switch (rxState) {
    case WAIT_START:
      if (data == PREAMBLE_BYTE) {
        if (preambleSeen < 255) preambleSeen++;
      } else if (data == START_BYTE && preambleSeen >= MIN_PREAMBLE_COUNT) {
        preambleSeen = 0;
        rxState = READ_TYPE;
      } else {
        preambleSeen = 0;
      }
      break;

    case READ_TYPE:
      frameType = data;

      if (frameType == TYPE_CAROUSEL_CHUNK || frameType == TYPE_CAROUSEL_PARITY) {
        rxState = READ_SIZE_MSB;
      } else {
        resetFrame();
      }
      break;

    case READ_SIZE_MSB:
      expectedSize = ((uint16_t)data) << 8;
      rxState = READ_SIZE_LSB;
      break;

    case READ_SIZE_LSB: {
      expectedSize |= data;
      bytesRemaining = expectedSize;
      computedCRC = 0xFFFF;

      if (payloadBuffer != nullptr) {
        free(payloadBuffer);
        payloadBuffer = nullptr;
      }

      uint16_t minHeader = (frameType == TYPE_CAROUSEL_PARITY) ? PARITY_HEADER_MIN : CAROUSEL_HEADER_MIN;

      if (expectedSize < minHeader) {
        badHeaderFrames++;
        Serial.println("RX_CAROUSEL_BAD_HEADER: too small");
        if (rxDiagnostics) printRxStats();
        resetFrame();
        break;
      }

      payloadBuffer = (uint8_t *)malloc(expectedSize);

      if (!payloadBuffer) {
        Serial.println("RX_ERROR: cannot allocate payload buffer");
        if (rxDiagnostics) printRxStats();
        resetFrame();
        break;
      }

      rxState = READ_CRC_MSB;
      break;
    }

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

      if (bytesRemaining > 0) bytesRemaining--;

      if (bytesRemaining == 0) {
        if (computedCRC == expectedCRC) {
          framesOk++;
          if (frameType == TYPE_CAROUSEL_CHUNK) {
            handleCarouselFrame();
          } else if (frameType == TYPE_CAROUSEL_PARITY) {
            handleParityFrame();
          }
        } else {
          badCrcFrames++;
          Serial.print("RX_CAROUSEL_BAD_CRC:");
          Serial.print(computedCRC, HEX);
          Serial.print(":expected=");
          Serial.println(expectedCRC, HEX);
          if (rxDiagnostics) {
            Serial.print("RX_CRC_CONTEXT:type=0x");
            Serial.print(frameType, HEX);
            Serial.print(":size=");
            Serial.print(expectedSize);
            Serial.print(":freq=");
            Serial.print(frequencyHz);
            Serial.print(":halfBitUs=");
            Serial.print(halfBitUs);
            Serial.print(":decodedBytes=");
            Serial.print(decodedBytes);
            Serial.print(":badCrc=");
            Serial.print(badCrcFrames);
            Serial.print(":unstableBits=");
            Serial.println(unstableBits);
          }
        }

        resetFrame();
      }

      break;
    }
  }
}

void handleParityFrame() {
  if (payloadBuffer == nullptr || expectedSize < PARITY_HEADER_MIN) {
    Serial.println("RX_CAROUSEL_BAD_HEADER: parity null/short");
    return;
  }

  uint16_t tid = readU16BE(payloadBuffer + 0);
  uint8_t kind = payloadBuffer[2];
  uint16_t groupStart = readU16BE(payloadBuffer + 3);
  uint16_t totalChunks = readU16BE(payloadBuffer + 5);
  uint32_t totalSize = readU32BE(payloadBuffer + 7);
  uint16_t chunkSize = readU16BE(payloadBuffer + 11);
  uint16_t fileCRC = readU16BE(payloadBuffer + 13);
  uint8_t nameLen = payloadBuffer[15];
  uint8_t groupCount = payloadBuffer[16];
  uint16_t parityLen = readU16BE(payloadBuffer + 17);

  uint32_t needed = (uint32_t)PARITY_HEADER_MIN + nameLen + parityLen;

  if (needed > expectedSize ||
      totalChunks == 0 ||
      chunkSize == 0 ||
      parityLen != chunkSize ||
      groupCount == 0 ||
      groupCount > 8 ||
      groupStart >= totalChunks) {
    Serial.print("RX_CAROUSEL_BAD_HEADER: parity tid=");
    Serial.print(tid);
    Serial.print(" group=");
    Serial.print(groupStart);
    Serial.print(" needed=");
    Serial.print(needed);
    Serial.print(" frame=");
    Serial.println(expectedSize);
    return;
  }

  Serial.print("RX_CAROUSEL_PARITY:");
  Serial.print(tid);
  Serial.print(":");
  Serial.print(kind);
  Serial.print(":");
  Serial.print(groupStart);
  Serial.print(":");
  Serial.print(totalChunks);
  Serial.print(":");
  Serial.print(totalSize);
  Serial.print(":");
  Serial.print(chunkSize);
  Serial.print(":");
  Serial.print(fileCRC, HEX);
  Serial.print(":");
  Serial.print(nameLen);
  Serial.print(":");
  Serial.print(groupCount);
  Serial.print(":");
  Serial.println(parityLen);

  if (nameLen > 0) {
    Serial.write(payloadBuffer + PARITY_HEADER_MIN, nameLen);
  }

  if (parityLen > 0) {
    Serial.write(payloadBuffer + PARITY_HEADER_MIN + nameLen, parityLen);
  }

  Serial.println();

  Serial.print("RX_CAROUSEL_PARITY_OK:");
  Serial.print(tid);
  Serial.print(":");
  Serial.print(groupStart);
  Serial.print(":");
  Serial.println(groupCount);
}

void handleCarouselFrame() {
  if (payloadBuffer == nullptr || expectedSize < CAROUSEL_HEADER_MIN) {
    Serial.println("RX_CAROUSEL_BAD_HEADER: null/short");
    return;
  }

  uint16_t tid = readU16BE(payloadBuffer + 0);
  uint8_t kind = payloadBuffer[2];
  uint16_t seq = readU16BE(payloadBuffer + 3);
  uint16_t totalChunks = readU16BE(payloadBuffer + 5);
  uint32_t totalSize = readU32BE(payloadBuffer + 7);
  uint16_t chunkLen = readU16BE(payloadBuffer + 11);
  uint16_t fileCRC = readU16BE(payloadBuffer + 13);
  uint8_t nameLen = payloadBuffer[15];

  uint32_t needed = (uint32_t)CAROUSEL_HEADER_MIN + nameLen + chunkLen;

  if (needed > expectedSize || totalChunks == 0 || seq >= totalChunks) {
    Serial.print("RX_CAROUSEL_BAD_HEADER: tid=");
    Serial.print(tid);
    Serial.print(" seq=");
    Serial.print(seq);
    Serial.print(" needed=");
    Serial.print(needed);
    Serial.print(" frame=");
    Serial.println(expectedSize);
    return;
  }

  Serial.print("RX_CAROUSEL_CHUNK:");
  Serial.print(tid);
  Serial.print(":");
  Serial.print(kind);
  Serial.print(":");
  Serial.print(seq);
  Serial.print(":");
  Serial.print(totalChunks);
  Serial.print(":");
  Serial.print(totalSize);
  Serial.print(":");
  Serial.print(chunkLen);
  Serial.print(":");
  Serial.print(fileCRC, HEX);
  Serial.print(":");
  Serial.println(nameLen);

  if (nameLen > 0) {
    Serial.write(payloadBuffer + CAROUSEL_HEADER_MIN, nameLen);
  }

  if (chunkLen > 0) {
    Serial.write(payloadBuffer + CAROUSEL_HEADER_MIN + nameLen, chunkLen);
  }

  Serial.println();

  Serial.print("RX_CAROUSEL_OK:");
  Serial.print(tid);
  Serial.print(":");
  Serial.print(seq);
  Serial.print(":");
  Serial.print(totalChunks);
  Serial.print(":");
  Serial.println(chunkLen);
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
