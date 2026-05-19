#include "driver/gpio.h"

#define RX_PIN 5
#define RX_ADC_PIN 34

const uint8_t START_BYTE = 0x02;
const uint8_t PREAMBLE_BYTE = 0xAA;
const uint8_t TYPE_CAROUSEL_CHUNK = 0x20;
const uint8_t TYPE_CAROUSEL_PARITY = 0x21;

const uint32_t MAX_FREQUENCY_HZ = 50000;
const uint8_t MIN_PREAMBLE_COUNT = 8;
const uint16_t CAROUSEL_HEADER_MIN = 16;
const uint16_t PARITY_HEADER_MIN = 19;

uint32_t frequencyHz = 9000;
uint32_t halfBitUs = 55;
bool rxDebug = false;
uint32_t statBytes = 0;
uint32_t statUnstableBits = 0;
uint32_t statBadCrc = 0;
uint32_t statGoodFrames = 0;
uint32_t statPreambleBytes = 0;
uint8_t statMaxPreambleRun = 0;

inline int readRxPin() {
  return gpio_get_level((gpio_num_t)RX_PIN);
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
  pinMode(RX_ADC_PIN, INPUT);
  analogReadResolution(12);

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

    if (cmd == "STATS") {
      printStats();
      handled = true;
      continue;
    }

    if (cmd == "RESETSTATS") {
      resetStats();
      Serial.println("RX_STATS_RESET");
      handled = true;
      continue;
    }

    if (cmd == "RXTEST" || cmd.startsWith("RXTEST=")) {
      uint32_t durationMs = 500;
      int eq = cmd.indexOf('=');
      if (eq >= 0) {
        durationMs = (uint32_t)cmd.substring(eq + 1).toInt();
      }
      runRxDigitalTest(durationMs);
      handled = true;
      continue;
    }

    if (cmd == "RXCAP" || cmd.startsWith("RXCAP=")) {
      uint32_t durationMs = 100;
      uint32_t sampleUs = 10;
      int eq = cmd.indexOf('=');
      if (eq >= 0) {
        String args = cmd.substring(eq + 1);
        int comma = args.indexOf(',');
        if (comma >= 0) {
          durationMs = (uint32_t)args.substring(0, comma).toInt();
          sampleUs = (uint32_t)args.substring(comma + 1).toInt();
        } else {
          durationMs = (uint32_t)args.toInt();
        }
      }
      runRxDigitalCapture(durationMs, sampleUs);
      handled = true;
      continue;
    }

    if (cmd == "ADCAP" || cmd.startsWith("ADCAP=")) {
      uint32_t durationMs = 100;
      uint32_t sampleUs = 100;
      uint16_t thresholdMv = 1000;
      int eq = cmd.indexOf('=');
      if (eq >= 0) {
        String args = cmd.substring(eq + 1);
        int firstComma = args.indexOf(',');
        int secondComma = firstComma >= 0 ? args.indexOf(',', firstComma + 1) : -1;
        if (firstComma >= 0) {
          durationMs = (uint32_t)args.substring(0, firstComma).toInt();
          if (secondComma >= 0) {
            sampleUs = (uint32_t)args.substring(firstComma + 1, secondComma).toInt();
            thresholdMv = (uint16_t)args.substring(secondComma + 1).toInt();
          } else {
            sampleUs = (uint32_t)args.substring(firstComma + 1).toInt();
          }
        } else {
          durationMs = (uint32_t)args.toInt();
        }
      }
      runRxAdcCapture(durationMs, sampleUs, thresholdMv);
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
    while (readRxPin() == HIGH) {
      if (handleSerialCommands()) return -2;
      yield();
    }

    while (readRxPin() == LOW) {
      if (handleSerialCommands()) return -2;
      yield();
    }

    uint32_t sampleDeadline = micros() + (halfBitUs / 2);
    waitUntilMicros(sampleDeadline);

    uint8_t value = 0;
    bool valid = true;

    for (int i = 7; i >= 0; i--) {
      sampleDeadline += halfBitUs;
      waitUntilMicros(sampleDeadline);
      bool first = majorityRead();

      sampleDeadline += halfBitUs;
      waitUntilMicros(sampleDeadline);
      bool second = majorityRead();

      if (first == second) {
        valid = false;
        statUnstableBits++;
        break;
      }

      bool bit = second;

      if (bit) value |= (1 << i);
    }

    if (!valid) {
      if (rxDebug) Serial.println("RX_ERROR: unstable Manchester bit");
      continue;
    }

    statBytes++;
    if (rxDebug) {
      Serial.print("RX_BYTE:0x");
      if (value < 16) Serial.print("0");
      Serial.println(value, HEX);
    }

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
        statPreambleBytes++;
        if (preambleSeen > statMaxPreambleRun) statMaxPreambleRun = preambleSeen;
      } else if (data == START_BYTE && preambleSeen >= MIN_PREAMBLE_COUNT) {
        if (rxDebug) {
          Serial.print("RX_FRAME_START:preamble=");
          Serial.println(preambleSeen);
        }
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
        Serial.println("RX_CAROUSEL_BAD_HEADER: too small");
        resetFrame();
        break;
      }

      payloadBuffer = (uint8_t *)malloc(expectedSize);

      if (!payloadBuffer) {
        Serial.println("RX_ERROR: cannot allocate payload buffer");
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
          if (frameType == TYPE_CAROUSEL_CHUNK) {
            handleCarouselFrame();
          } else if (frameType == TYPE_CAROUSEL_PARITY) {
            handleParityFrame();
          }
        } else {
          statBadCrc++;
          Serial.print("RX_CAROUSEL_BAD_CRC:");
          Serial.print(computedCRC, HEX);
          Serial.print(":expected=");
          Serial.println(expectedCRC, HEX);
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
  statGoodFrames++;
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
  statGoodFrames++;
}

void resetStats() {
  statBytes = 0;
  statUnstableBits = 0;
  statBadCrc = 0;
  statGoodFrames = 0;
  statPreambleBytes = 0;
  statMaxPreambleRun = 0;
}

void printStats() {
  Serial.print("RX_STATS:freq=");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.print(halfBitUs);
  Serial.print(":pin=");
  Serial.print(RX_PIN);
  Serial.print(":raw=");
  Serial.print(readRxPin());
  Serial.print(":bytes=");
  Serial.print(statBytes);
  Serial.print(":unstableBits=");
  Serial.print(statUnstableBits);
  Serial.print(":badCrc=");
  Serial.print(statBadCrc);
  Serial.print(":framesOk=");
  Serial.print(statGoodFrames);
  Serial.print(":preambleBytes=");
  Serial.print(statPreambleBytes);
  Serial.print(":maxPreambleRun=");
  Serial.println(statMaxPreambleRun);
}

void runRxDigitalTest(uint32_t durationMs) {
  if (durationMs < 50) durationMs = 50;
  if (durationMs > 5000) durationMs = 5000;

  uint32_t start = millis();
  uint32_t samples = 0;
  uint32_t highs = 0;
  uint32_t lows = 0;
  uint32_t transitions = 0;
  int last = readRxPin();

  while ((uint32_t)(millis() - start) < durationMs) {
    int current = readRxPin();
    if (current) highs++;
    else lows++;
    if (current != last) {
      transitions++;
      last = current;
    }
    samples++;
    delayMicroseconds(50);
  }

  Serial.print("RX_DIGITAL_TEST:durationMs=");
  Serial.print(durationMs);
  Serial.print(":samples=");
  Serial.print(samples);
  Serial.print(":high=");
  Serial.print(highs);
  Serial.print(":low=");
  Serial.print(lows);
  Serial.print(":transitions=");
  Serial.print(transitions);
  Serial.print(":final=");
  Serial.println(readRxPin());
}

void runRxDigitalCapture(uint32_t durationMs, uint32_t sampleUs) {
  if (durationMs < 5) durationMs = 5;
  if (durationMs > 2000) durationMs = 2000;
  if (sampleUs < 2) sampleUs = 2;
  if (sampleUs > 1000) sampleUs = 1000;

  uint32_t startUs = micros();
  uint32_t endUs = startUs + (durationMs * 1000UL);
  uint32_t samples = 0;
  uint32_t highs = 0;
  uint32_t lows = 0;
  uint32_t transitions = 0;
  uint32_t minRunUs = 0xFFFFFFFF;
  uint32_t maxRunUs = 0;
  uint32_t lastEdgeUs = startUs;
  int last = readRxPin();

  while ((int32_t)(micros() - endUs) < 0) {
    uint32_t now = micros();
    int current = readRxPin();
    if (current) highs++;
    else lows++;
    if (current != last) {
      uint32_t runUs = now - lastEdgeUs;
      if (runUs < minRunUs) minRunUs = runUs;
      if (runUs > maxRunUs) maxRunUs = runUs;
      transitions++;
      lastEdgeUs = now;
      last = current;
    }
    samples++;
    delayMicroseconds(sampleUs);
  }

  if (transitions == 0) minRunUs = 0;

  Serial.print("RX_DIGITAL_CAPTURE:durationMs=");
  Serial.print(durationMs);
  Serial.print(":sampleUs=");
  Serial.print(sampleUs);
  Serial.print(":freq=");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.print(halfBitUs);
  Serial.print(":samples=");
  Serial.print(samples);
  Serial.print(":high=");
  Serial.print(highs);
  Serial.print(":low=");
  Serial.print(lows);
  Serial.print(":transitions=");
  Serial.print(transitions);
  Serial.print(":minRunUs=");
  Serial.print(minRunUs);
  Serial.print(":maxRunUs=");
  Serial.print(maxRunUs);
  Serial.print(":final=");
  Serial.println(readRxPin());
}

void runRxAdcCapture(uint32_t durationMs, uint32_t sampleUs, uint16_t thresholdMv) {
  if (durationMs < 5) durationMs = 5;
  if (durationMs > 2000) durationMs = 2000;
  if (sampleUs < 50) sampleUs = 50;
  if (sampleUs > 5000) sampleUs = 5000;
  if (thresholdMv > 3300) thresholdMv = 3300;

  uint32_t startUs = micros();
  uint32_t endUs = startUs + (durationMs * 1000UL);
  uint32_t samples = 0;
  uint32_t above = 0;
  uint32_t below = 0;
  uint32_t transitions = 0;
  uint32_t sumMv = 0;
  uint16_t minMv = 5000;
  uint16_t maxMv = 0;
  int lastLevel = -1;

  while ((int32_t)(micros() - endUs) < 0) {
    uint16_t mv = analogReadMilliVolts(RX_ADC_PIN);
    int level = mv >= thresholdMv ? 1 : 0;
    if (mv < minMv) minMv = mv;
    if (mv > maxMv) maxMv = mv;
    sumMv += mv;
    if (level) above++;
    else below++;
    if (lastLevel >= 0 && level != lastLevel) transitions++;
    lastLevel = level;
    samples++;
    delayMicroseconds(sampleUs);
  }

  uint32_t avgMv = samples ? (sumMv / samples) : 0;

  Serial.print("RX_ADC_CAPTURE:durationMs=");
  Serial.print(durationMs);
  Serial.print(":sampleUs=");
  Serial.print(sampleUs);
  Serial.print(":pin=");
  Serial.print(RX_ADC_PIN);
  Serial.print(":thresholdMv=");
  Serial.print(thresholdMv);
  Serial.print(":samples=");
  Serial.print(samples);
  Serial.print(":minMv=");
  Serial.print(minMv);
  Serial.print(":maxMv=");
  Serial.print(maxMv);
  Serial.print(":avgMv=");
  Serial.print(avgMv);
  Serial.print(":above=");
  Serial.print(above);
  Serial.print(":below=");
  Serial.print(below);
  Serial.print(":transitions=");
  Serial.println(transitions);
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
