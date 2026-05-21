#include "driver/gpio.h"

#define RX_PIN 5

const uint8_t PREAMBLE_BYTE = 0x55;
const uint8_t START_BYTE = 0x02;
const uint8_t STOP_BYTE = 0x03;
const uint8_t TYPE_TEXT = 0x01;

const uint8_t MIN_PREAMBLE_COUNT = 4;
const uint16_t MAX_PAYLOAD_LEN = 260;
const uint32_t MIN_FREQUENCY_HZ = 1;
const uint32_t MAX_FREQUENCY_HZ = 15000;

uint32_t frequencyHz = 1000;
uint32_t halfBitUs = 500;
bool rxInverted = false;
bool debugBits = true;
bool debugBytes = true;

uint32_t statBits = 0;
uint32_t statBytes = 0;
uint32_t statUnstable = 0;
uint32_t statPacketsOk = 0;
uint32_t statPacketsFail = 0;
uint8_t preambleRun = 0;

enum RxState {
  WAIT_START,
  READ_TYPE,
  READ_LEN_MSB,
  READ_LEN_LSB,
  READ_PAYLOAD,
  READ_CRC_MSB,
  READ_CRC_LSB,
  READ_STOP
};

RxState state = WAIT_START;
uint8_t packetType = 0;
uint16_t expectedLen = 0;
uint16_t payloadIndex = 0;
uint8_t payload[MAX_PAYLOAD_LEN];
uint16_t expectedCrc = 0;

inline int rawPin() {
  return gpio_get_level((gpio_num_t)RX_PIN);
}

inline bool readLogic() {
  int value = rawPin();
  return rxInverted ? !value : value;
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);
  pinMode(RX_PIN, INPUT);
  setFrequency(frequencyHz);
  Serial.println("RX_TEXT_DEBUG_READY");
  Serial.println("COMMANDS:FREQ=1000,INV=0,DEBUGBITS=1,DEBUGBYTES=1,RXCAP=1000,50,STATS,RESET");
}

void loop() {
  if (handleSerialCommands()) return;

  int received = receiveManchesterByte();
  if (received < 0) return;

  processByte((uint8_t)received);
}

bool handleSerialCommands() {
  if (!Serial.available()) return false;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return true;

  if (line.startsWith("FREQ=")) {
    setFrequency((uint32_t)line.substring(5).toInt());
    resetPacket("freq change");
    return true;
  }

  if (line.startsWith("INV=")) {
    rxInverted = line.substring(4).toInt() != 0;
    Serial.print("RX_INV=");
    Serial.println(rxInverted ? 1 : 0);
    resetPacket("inv change");
    return true;
  }

  if (line.startsWith("DEBUGBITS=")) {
    debugBits = line.substring(10).toInt() != 0;
    Serial.print("RX_DEBUGBITS=");
    Serial.println(debugBits ? 1 : 0);
    return true;
  }

  if (line.startsWith("DEBUGBYTES=")) {
    debugBytes = line.substring(11).toInt() != 0;
    Serial.print("RX_DEBUGBYTES=");
    Serial.println(debugBytes ? 1 : 0);
    return true;
  }

  if (line == "STATS") {
    printStats();
    return true;
  }

  if (line == "RESET") {
    resetStats();
    resetPacket("manual reset");
    Serial.println("RX_RESET_DONE");
    return true;
  }

  if (line == "STATUS") {
    printStatus();
    return true;
  }

  if (line.startsWith("RXCAP")) {
    runCapture(line);
    return true;
  }

  Serial.print("RX_UNKNOWN:");
  Serial.println(line);
  return true;
}

void setFrequency(uint32_t f) {
  if (f < MIN_FREQUENCY_HZ) f = MIN_FREQUENCY_HZ;
  if (f > MAX_FREQUENCY_HZ) f = MAX_FREQUENCY_HZ;

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);
  if (halfBitUs < 1) halfBitUs = 1;

  Serial.print("RX_FREQ:");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.println(halfBitUs);
}

int receiveManchesterByte() {
  while (readLogic() == HIGH) {
    if (Serial.available()) return -1;
    yield();
  }
  while (readLogic() == LOW) {
    if (Serial.available()) return -1;
    yield();
  }

  delayMicroseconds(halfBitUs / 2);

  uint8_t value = 0;

  for (int i = 7; i >= 0; i--) {
    delayMicroseconds(halfBitUs);
    bool first = majorityRead();

    delayMicroseconds(halfBitUs);
    bool second = majorityRead();

    if (first == second) {
      statUnstable++;
      Serial.print("RX_BIT_BAD:first=");
      Serial.print(first ? 1 : 0);
      Serial.print(":second=");
      Serial.println(second ? 1 : 0);
      return -2;
    }

    bool bit = second;
    if (bit) value |= (1 << i);
    statBits++;

    if (debugBits) {
      Serial.print("RX_BIT:");
      Serial.println(bit ? 1 : 0);
    }
  }

  statBytes++;
  if (debugBytes) printRxByte(value);
  return value;
}

bool majorityRead() {
  uint8_t ones = 0;
  uint32_t spreadUs = halfBitUs / 12;
  if (spreadUs < 1) spreadUs = 1;
  if (spreadUs > 8) spreadUs = 8;

  if (readLogic()) ones++;
  delayMicroseconds(spreadUs);
  if (readLogic()) ones++;
  delayMicroseconds(spreadUs);
  if (readLogic()) ones++;

  return ones >= 2;
}

void processByte(uint8_t data) {
  switch (state) {
    case WAIT_START:
      if (data == PREAMBLE_BYTE) {
        if (preambleRun < 255) preambleRun++;
        Serial.print("RX_PREAMBLE:run=");
        Serial.println(preambleRun);
      } else if (data == START_BYTE && preambleRun >= MIN_PREAMBLE_COUNT) {
        Serial.print("RX_PACKET_START:preamble=");
        Serial.println(preambleRun);
        state = READ_TYPE;
        preambleRun = 0;
      } else {
        if (preambleRun > 0) {
          Serial.print("RX_PREAMBLE_BROKEN:run=");
          Serial.print(preambleRun);
          Serial.print(":byte=0x");
          printHex2(data);
          Serial.println();
        }
        preambleRun = 0;
      }
      break;

    case READ_TYPE:
      packetType = data;
      state = READ_LEN_MSB;
      break;

    case READ_LEN_MSB:
      expectedLen = ((uint16_t)data) << 8;
      state = READ_LEN_LSB;
      break;

    case READ_LEN_LSB:
      expectedLen |= data;
      payloadIndex = 0;
      if (expectedLen > MAX_PAYLOAD_LEN) {
        Serial.print("RX_PACKET_FAIL:len_too_large=");
        Serial.println(expectedLen);
        statPacketsFail++;
        resetPacket("len too large");
      } else {
        Serial.print("RX_PAYLOAD_EXPECT:type=");
        Serial.print(packetType);
        Serial.print(":len=");
        Serial.println(expectedLen);
        state = expectedLen == 0 ? READ_CRC_MSB : READ_PAYLOAD;
      }
      break;

    case READ_PAYLOAD:
      payload[payloadIndex++] = data;
      if (payloadIndex >= expectedLen) state = READ_CRC_MSB;
      break;

    case READ_CRC_MSB:
      expectedCrc = ((uint16_t)data) << 8;
      state = READ_CRC_LSB;
      break;

    case READ_CRC_LSB:
      expectedCrc |= data;
      state = READ_STOP;
      break;

    case READ_STOP:
      if (data != STOP_BYTE) {
        Serial.print("RX_PACKET_INCOMPLETE:bad_stop=0x");
        printHex2(data);
        Serial.println();
        statPacketsFail++;
        resetPacket("bad stop");
        return;
      }
      finishPacket();
      break;
  }
}

void finishPacket() {
  uint16_t gotCrc = packetCrc(packetType, expectedLen, payload);

  if (gotCrc != expectedCrc) {
    Serial.print("RX_PACKET_FAIL:crc expected=0x");
    printHex4(expectedCrc);
    Serial.print(":got=0x");
    printHex4(gotCrc);
    Serial.print(":type=");
    Serial.print(packetType);
    Serial.print(":len=");
    Serial.println(expectedLen);
    statPacketsFail++;
    resetPacket("crc fail");
    return;
  }

  statPacketsOk++;
  Serial.print("RX_PACKET_OK:type=");
  Serial.print(packetType);
  Serial.print(":len=");
  Serial.print(expectedLen);
  Serial.print(":crc=0x");
  printHex4(gotCrc);

  if (packetType == TYPE_TEXT) {
    Serial.print(":text=");
    for (uint16_t i = 0; i < expectedLen; i++) {
      char c = (char)payload[i];
      if (c == '\r' || c == '\n') Serial.print(' ');
      else Serial.print(c);
    }
  }

  Serial.println();
  resetPacket("ok");
}

void resetPacket(const char *reason) {
  state = WAIT_START;
  packetType = 0;
  expectedLen = 0;
  payloadIndex = 0;
  expectedCrc = 0;
  preambleRun = 0;
  Serial.print("RX_STATE:WAIT_START:reason=");
  Serial.println(reason);
}

uint16_t crc16Update(uint16_t crc, uint8_t data) {
  crc ^= (uint16_t)data << 8;
  for (uint8_t i = 0; i < 8; i++) {
    if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
    else crc <<= 1;
  }
  return crc & 0xFFFF;
}

uint16_t packetCrc(uint8_t type, uint16_t len, const uint8_t *data) {
  uint16_t crc = 0xFFFF;
  crc = crc16Update(crc, type);
  crc = crc16Update(crc, (len >> 8) & 0xFF);
  crc = crc16Update(crc, len & 0xFF);
  for (uint16_t i = 0; i < len; i++) crc = crc16Update(crc, data[i]);
  return crc & 0xFFFF;
}

void runCapture(String line) {
  uint32_t durationMs = 1000;
  uint32_t sampleUs = 50;
  int eq = line.indexOf('=');
  if (eq >= 0) {
    String args = line.substring(eq + 1);
    int comma = args.indexOf(',');
    if (comma >= 0) {
      durationMs = (uint32_t)args.substring(0, comma).toInt();
      sampleUs = (uint32_t)args.substring(comma + 1).toInt();
    } else {
      durationMs = (uint32_t)args.toInt();
    }
  }
  if (durationMs < 1) durationMs = 1;
  if (durationMs > 10000) durationMs = 10000;
  if (sampleUs < 5) sampleUs = 5;
  if (sampleUs > 5000) sampleUs = 5000;

  uint32_t start = micros();
  uint32_t durationUs = durationMs * 1000UL;
  uint32_t samples = 0;
  uint32_t highs = 0;
  uint32_t lows = 0;
  uint32_t transitions = 0;
  bool last = readLogic();
  String bits = "";

  while ((uint32_t)(micros() - start) < durationUs) {
    bool value = readLogic();
    if (value) highs++;
    else lows++;
    if (value != last) transitions++;
    last = value;
    samples++;
    if (bits.length() < 256) bits += value ? "1" : "0";
    delayMicroseconds(sampleUs);
  }

  Serial.print("RXCAP:samples=");
  Serial.print(samples);
  Serial.print(":high=");
  Serial.print(highs);
  Serial.print(":low=");
  Serial.print(lows);
  Serial.print(":transitions=");
  Serial.print(transitions);
  Serial.print(":sampleUs=");
  Serial.print(sampleUs);
  Serial.print(":bits=");
  Serial.println(bits);
}

void printStats() {
  Serial.print("RX_STATS:freq=");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.print(halfBitUs);
  Serial.print(":raw=");
  Serial.print(rawPin());
  Serial.print(":logic=");
  Serial.print(readLogic() ? 1 : 0);
  Serial.print(":bits=");
  Serial.print(statBits);
  Serial.print(":bytes=");
  Serial.print(statBytes);
  Serial.print(":unstable=");
  Serial.print(statUnstable);
  Serial.print(":ok=");
  Serial.print(statPacketsOk);
  Serial.print(":fail=");
  Serial.println(statPacketsFail);
}

void printStatus() {
  Serial.print("RX_STATUS:freq=");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.print(halfBitUs);
  Serial.print(":inv=");
  Serial.print(rxInverted ? 1 : 0);
  Serial.print(":debugBits=");
  Serial.print(debugBits ? 1 : 0);
  Serial.print(":debugBytes=");
  Serial.println(debugBytes ? 1 : 0);
}

void resetStats() {
  statBits = 0;
  statBytes = 0;
  statUnstable = 0;
  statPacketsOk = 0;
  statPacketsFail = 0;
}

void printRxByte(uint8_t value) {
  Serial.print("RX_BYTE:0x");
  printHex2(value);
  Serial.print(":");
  for (int i = 7; i >= 0; i--) Serial.print((value >> i) & 1);
  Serial.println();
}

void printHex2(uint8_t value) {
  if (value < 16) Serial.print("0");
  Serial.print(value, HEX);
}

void printHex4(uint16_t value) {
  if (value < 0x1000) Serial.print("0");
  if (value < 0x0100) Serial.print("0");
  if (value < 0x0010) Serial.print("0");
  Serial.print(value, HEX);
}
