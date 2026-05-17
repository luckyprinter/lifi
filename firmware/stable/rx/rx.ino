#include "driver/gpio.h"

#define RX_PIN 5

const uint8_t START_BYTE = 0x02;
const uint8_t PREAMBLE_BYTE = 0xAA;
const uint8_t TYPE_CAROUSEL_CHUNK = 0x20;
const uint8_t TYPE_CAROUSEL_PARITY = 0x21;
const char *RX_FIRMWARE_ID = "RX_DIAG_EDGE_HL_20260517";

const uint32_t MAX_FREQUENCY_HZ = 50000;
const uint8_t MIN_PREAMBLE_COUNT = 8;
const uint16_t CAROUSEL_HEADER_MIN = 16;
const uint16_t PARITY_HEADER_MIN = 19;

uint32_t frequencyHz = 9000;
uint32_t halfBitUs = 55;
bool rxDebug = false;
bool syncHighToLow = true;
uint8_t sampleOffsetPercent = 55;
uint32_t decodedBytes = 0;
uint32_t invalidManchester = 0;
uint32_t candidateStarts = 0;
uint32_t frameStarts = 0;
uint32_t chunkFramesOk = 0;
uint32_t parityFramesOk = 0;
uint32_t badCrcFrames = 0;
uint32_t badHeaderFrames = 0;
uint32_t unknownTypeFrames = 0;
uint32_t lastStatsMs = 0;

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

  setFrequency(frequencyHz);

  Serial.print("ESP32 RX Ready - one-way carousel protocol | FW=");
  Serial.println(RX_FIRMWARE_ID);
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

    if (cmd.startsWith("STATS")) {
      printRxStats();
      handled = true;
      continue;
    }

    if (cmd.startsWith("FW?") || cmd.startsWith("VERSION")) {
      Serial.print("RX_FW:");
      Serial.println(RX_FIRMWARE_ID);
      handled = true;
      continue;
    }

    if (cmd.startsWith("EDGE=")) {
      String edge = cmd.substring(5);
      edge.trim();
      edge.toUpperCase();

      if (edge == "HL" || edge == "HIGH_TO_LOW") {
        syncHighToLow = true;
        Serial.println("RX sync edge = HIGH_TO_LOW");
      } else if (edge == "LH" || edge == "LOW_TO_HIGH") {
        syncHighToLow = false;
        Serial.println("RX sync edge = LOW_TO_HIGH");
      } else {
        Serial.print("RX_ERROR: unknown EDGE=");
        Serial.println(edge);
      }

      resetFrame();
      handled = true;
      continue;
    }

    if (cmd.startsWith("PHASE=")) {
      int value = cmd.substring(6).toInt();

      if (value < 35) value = 35;
      if (value > 80) value = 80;

      sampleOffsetPercent = (uint8_t)value;
      Serial.print("RX sample phase = ");
      Serial.print(sampleOffsetPercent);
      Serial.println("%");
      resetFrame();
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
  uint32_t highCount = 0;
  uint32_t lowCount = 0;
  uint32_t transitions = 0;
  int last = readRxPin();

  Serial.println("RX_INPUT_TEST_START");

  while (millis() - startMs < durationMs) {
    int current = readRxPin();

    if (current == HIGH) highCount++;
    else lowCount++;

    if (current != last) {
      transitions++;
      last = current;
    }

    samples++;
    delayMicroseconds(sampleGapUs);
  }

  Serial.print("RX_INPUT_TEST_DONE:samples=");
  Serial.print(samples);
  Serial.print(":high=");
  Serial.print(highCount);
  Serial.print(":low=");
  Serial.print(lowCount);
  Serial.print(":transitions=");
  Serial.println(transitions);
}

void printRxStats() {
  Serial.print("RX_STATS:freq=");
  Serial.print(frequencyHz);
  Serial.print(":fw=");
  Serial.print(RX_FIRMWARE_ID);
  Serial.print(":halfBitUs=");
  Serial.print(halfBitUs);
  Serial.print(":edge=");
  Serial.print(syncHighToLow ? "HL" : "LH");
  Serial.print(":phase=");
  Serial.print(sampleOffsetPercent);
  Serial.print(":pin=");
  Serial.print(readRxPin());
  Serial.print(":decodedBytes=");
  Serial.print(decodedBytes);
  Serial.print(":invalidManchester=");
  Serial.print(invalidManchester);
  Serial.print(":candidateStarts=");
  Serial.print(candidateStarts);
  Serial.print(":frameStarts=");
  Serial.print(frameStarts);
  Serial.print(":chunkOk=");
  Serial.print(chunkFramesOk);
  Serial.print(":parityOk=");
  Serial.print(parityFramesOk);
  Serial.print(":badCrc=");
  Serial.print(badCrcFrames);
  Serial.print(":badHeader=");
  Serial.print(badHeaderFrames);
  Serial.print(":unknownType=");
  Serial.print(unknownTypeFrames);
  Serial.print(":state=");
  Serial.print((int)rxState);
  Serial.print(":preambleSeen=");
  Serial.println(preambleSeen);
}

void printRxStatsIfDue() {
  if (!rxDebug) return;

  uint32_t now = millis();
  if (now - lastStatsMs < 1000) return;

  lastStatsMs = now;
  printRxStats();
}

int receiveManchesterByte() {
  while (true) {
    if (syncHighToLow) {
      // Current TEPT4400 divider with TX idle LED ON usually idles LOW.
      // A Manchester byte starts when TX briefly turns the LED OFF then ON,
      // which appears at the RX GPIO as HIGH then LOW. Sync on that falling
      // edge so the following samples align with the data bit centers.
      while (readRxPin() == LOW) {
        if (handleSerialCommands()) return -2;
        printRxStatsIfDue();
        yield();
      }

      while (readRxPin() == HIGH) {
        if (handleSerialCommands()) return -2;
        printRxStatsIfDue();
        yield();
      }
    } else {
      // Legacy/inverted receiver wiring path.
      while (readRxPin() == HIGH) {
        if (handleSerialCommands()) return -2;
        printRxStatsIfDue();
        yield();
      }

      while (readRxPin() == LOW) {
        if (handleSerialCommands()) return -2;
        printRxStatsIfDue();
        yield();
      }
    }

    candidateStarts++;

    // The TEPT4400 plus a large load resistor such as 47k can delay threshold
    // crossings. A configurable phase lets us sample slightly before or after
    // the ideal center. Start near center; tune with PHASE=45..70 if CRC fails.
    uint32_t sampleDeadline = micros() + ((uint32_t)halfBitUs * sampleOffsetPercent / 100);
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
        break;
      }

      bool bit = second;

      if (bit) value |= (1 << i);
    }

    if (!valid) {
      invalidManchester++;
      if (rxDebug) Serial.println("RX_ERROR: unstable Manchester bit");
      continue;
    }

    decodedBytes++;
    if (rxDebug && decodedBytes % 64 == 0) {
      Serial.print("RX_DEBUG_DECODED_BYTES:");
      Serial.println(decodedBytes);
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
      } else if (data == START_BYTE && preambleSeen >= MIN_PREAMBLE_COUNT) {
        preambleSeen = 0;
        frameStarts++;
        if (rxDebug) Serial.println("RX_DEBUG_FRAME_START");
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
        unknownTypeFrames++;
        if (rxDebug) {
          Serial.print("RX_DEBUG_UNKNOWN_TYPE:0x");
          Serial.println(frameType, HEX);
        }
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
          badCrcFrames++;
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
    badHeaderFrames++;
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
  parityFramesOk++;
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
    badHeaderFrames++;
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
  chunkFramesOk++;
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
