#include "driver/gpio.h"

#define RX_PIN 5

const uint8_t SOF = 0x7E;
const uint8_t TYPE_END = 0x00;
const uint8_t TYPE_TEXT = 0x01;
const uint8_t TYPE_IMAGE = 0x02;
const uint8_t TYPE_AUDIO = 0x03;

const uint32_t MAX_FREQUENCY_HZ = 50000;
const uint8_t MAX_PAYLOAD_LEN = 64;

uint32_t frequencyHz = 9000;
uint32_t halfBitUs = 55;
bool rxDebug = false;
bool invertRx = true;
uint8_t samplePhasePercent = 50;

uint32_t statBytes = 0;
uint32_t statPacketsOk = 0;
uint32_t statCrcFail = 0;
uint32_t statUnstable = 0;
uint32_t statSof = 0;
uint32_t statDebugSuppressed = 0;
uint32_t lastDebugMs = 0;

enum State {
  WAIT_SOF,
  READ_TYPE,
  READ_SEQ,
  READ_LEN,
  READ_DATA,
  READ_CRC
};

State state = WAIT_SOF;
uint8_t packetType = 0;
uint8_t packetSeq = 0;
uint8_t packetLen = 0;
uint8_t packetIdx = 0;
uint8_t packetCrc = 0;
uint8_t payload[MAX_PAYLOAD_LEN];
String textBuffer = "";

inline int rawRxPin() {
  return gpio_get_level((gpio_num_t)RX_PIN);
}

inline int readRxPin() {
  int level = rawRxPin();
  return invertRx ? !level : level;
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);

  pinMode(RX_PIN, INPUT);
  setFrequency(frequencyHz);
  Serial.println("PACKET_CRC_RX_READY:gpio5:LM393_DEFAULT_INV=1");
}

void loop() {
  handleSerialCommands();

  int received = receiveManchesterByte();
  if (received < 0) return;

  processByte((uint8_t)received);
}

bool handleSerialCommands() {
  bool handled = false;

  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) continue;

    if (cmd.startsWith("FREQ=")) {
      setFrequency(cmd.substring(5).toInt());
      resetState();
      handled = true;
      continue;
    }

    if (cmd.startsWith("DEBUG=")) {
      rxDebug = (cmd.substring(6).toInt() != 0);
      Serial.print("RX_DEBUG=");
      Serial.println(rxDebug ? 1 : 0);
      handled = true;
      continue;
    }

    if (cmd.startsWith("INV=")) {
      invertRx = (cmd.substring(4).toInt() != 0);
      resetState();
      Serial.print("RX_INV=");
      Serial.println(invertRx ? 1 : 0);
      handled = true;
      continue;
    }

    if (cmd.startsWith("PHASE=")) {
      int requested = cmd.substring(6).toInt();
      if (requested < 20) requested = 20;
      if (requested > 80) requested = 80;
      samplePhasePercent = (uint8_t)requested;
      resetState();
      Serial.print("RX_PHASE=");
      Serial.println(samplePhasePercent);
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

    Serial.print("RX_UNKNOWN_CMD:");
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

    delayMicroseconds(phaseDelayUs());

    uint8_t value = 0;

    for (int i = 7; i >= 0; i--) {
      delayMicroseconds(halfBitUs);
      bool first = majorityRead();

      delayMicroseconds(halfBitUs);
      bool second = majorityRead();

      if (first == second) {
        statUnstable++;
        debugUnstableBit();
        return -1;
      }

      if (second) value |= (1 << i);
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

uint32_t phaseDelayUs() {
  uint32_t delayUs = (halfBitUs * (uint32_t)samplePhasePercent) / 100UL;
  if (delayUs < 1) delayUs = 1;
  return delayUs;
}

void debugUnstableBit() {
  if (!rxDebug) return;

  uint32_t now = millis();
  if (now - lastDebugMs < 250) {
    statDebugSuppressed++;
    return;
  }

  Serial.print("RX_ERROR:unstable_manchester_bit:raw=");
  Serial.print(rawRxPin());
  Serial.print(":level=");
  Serial.print(readRxPin());
  Serial.print(":inv=");
  Serial.print(invertRx ? 1 : 0);
  Serial.print(":phase=");
  Serial.print(samplePhasePercent);
  Serial.print(":suppressed=");
  Serial.println(statDebugSuppressed);

  statDebugSuppressed = 0;
  lastDebugMs = now;
}

void processByte(uint8_t value) {
  switch (state) {
    case WAIT_SOF:
      if (value == SOF) {
        statSof++;
        state = READ_TYPE;
      }
      break;

    case READ_TYPE:
      packetType = value;
      packetCrc = packetType;
      state = READ_SEQ;
      break;

    case READ_SEQ:
      packetSeq = value;
      packetCrc ^= packetSeq;
      state = READ_LEN;
      break;

    case READ_LEN:
      packetLen = value;
      packetCrc ^= packetLen;
      packetIdx = 0;
      if (packetLen > MAX_PAYLOAD_LEN) {
        Serial.print("RX_PACKET_BAD_LEN:");
        Serial.println(packetLen);
        resetState();
      } else if (packetLen == 0) {
        state = READ_CRC;
      } else {
        state = READ_DATA;
      }
      break;

    case READ_DATA:
      payload[packetIdx++] = value;
      packetCrc ^= value;
      if (packetIdx >= packetLen) state = READ_CRC;
      break;

    case READ_CRC:
      if (packetCrc == value) {
        statPacketsOk++;
        handlePacket();
      } else {
        statCrcFail++;
        Serial.print("RX_PACKET_CRC_FAIL:computed=0x");
        if (packetCrc < 16) Serial.print("0");
        Serial.print(packetCrc, HEX);
        Serial.print(":expected=0x");
        if (value < 16) Serial.print("0");
        Serial.println(value, HEX);
      }
      resetState();
      break;
  }
}

void handlePacket() {
  Serial.print("RX_PACKET_OK:type=");
  Serial.print(packetType);
  Serial.print(":seq=");
  Serial.print(packetSeq);
  Serial.print(":len=");
  Serial.println(packetLen);

  if (packetType == TYPE_TEXT) {
    for (uint8_t i = 0; i < packetLen; i++) {
      textBuffer += (char)payload[i];
    }
    Serial.print("RX_TEXT_CHUNK:");
    Serial.write(payload, packetLen);
    Serial.println();
  } else if (packetType == TYPE_END) {
    Serial.print("RX_MESSAGE_END:text=");
    Serial.println(textBuffer);
    textBuffer = "";
  } else if (packetType == TYPE_IMAGE || packetType == TYPE_AUDIO) {
    Serial.println("RX_PACKET_BINARY_TYPE_UNHANDLED_IN_TEXT_TEST");
  }
}

void resetState() {
  state = WAIT_SOF;
  packetType = 0;
  packetSeq = 0;
  packetLen = 0;
  packetIdx = 0;
  packetCrc = 0;
}

void resetStats() {
  statBytes = 0;
  statPacketsOk = 0;
  statCrcFail = 0;
  statUnstable = 0;
  statSof = 0;
  statDebugSuppressed = 0;
}

void printStats() {
  Serial.print("RX_PACKET_STATS:freq=");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.print(halfBitUs);
  Serial.print(":pin=");
  Serial.print(RX_PIN);
  Serial.print(":raw=");
  Serial.print(rawRxPin());
  Serial.print(":level=");
  Serial.print(readRxPin());
  Serial.print(":inv=");
  Serial.print(invertRx ? 1 : 0);
  Serial.print(":phase=");
  Serial.print(samplePhasePercent);
  Serial.print(":bytes=");
  Serial.print(statBytes);
  Serial.print(":sof=");
  Serial.print(statSof);
  Serial.print(":ok=");
  Serial.print(statPacketsOk);
  Serial.print(":crcFail=");
  Serial.print(statCrcFail);
  Serial.print(":unstable=");
  Serial.print(statUnstable);
  Serial.print(":debugSuppressed=");
  Serial.println(statDebugSuppressed);
}

void runRxDigitalCapture(uint32_t durationMs, uint32_t sampleUs) {
  if (durationMs < 5) durationMs = 5;
  if (durationMs > 5000) durationMs = 5000;
  if (sampleUs < 2) sampleUs = 2;
  if (sampleUs > 1000) sampleUs = 1000;

  uint32_t startUs = micros();
  uint32_t endUs = startUs + (durationMs * 1000UL);
  uint32_t samples = 0;
  uint32_t highs = 0;
  uint32_t lows = 0;
  uint32_t transitions = 0;
  uint32_t rawHighs = 0;
  uint32_t rawLows = 0;
  uint32_t rawTransitions = 0;
  int last = readRxPin();
  int rawLast = rawRxPin();

  while ((int32_t)(micros() - endUs) < 0) {
    int rawCurrent = rawRxPin();
    int current = readRxPin();
    if (current) highs++;
    else lows++;
    if (rawCurrent) rawHighs++;
    else rawLows++;
    if (current != last) {
      transitions++;
      last = current;
    }
    if (rawCurrent != rawLast) {
      rawTransitions++;
      rawLast = rawCurrent;
    }
    samples++;
    delayMicroseconds(sampleUs);
  }

  Serial.print("RX_PACKET_CAPTURE:durationMs=");
  Serial.print(durationMs);
  Serial.print(":sampleUs=");
  Serial.print(sampleUs);
  Serial.print(":freq=");
  Serial.print(frequencyHz);
  Serial.print(":samples=");
  Serial.print(samples);
  Serial.print(":high=");
  Serial.print(highs);
  Serial.print(":low=");
  Serial.print(lows);
  Serial.print(":transitions=");
  Serial.print(transitions);
  Serial.print(":rawHigh=");
  Serial.print(rawHighs);
  Serial.print(":rawLow=");
  Serial.print(rawLows);
  Serial.print(":rawTransitions=");
  Serial.print(rawTransitions);
  Serial.print(":final=");
  Serial.print(readRxPin());
  Serial.print(":rawFinal=");
  Serial.println(rawRxPin());
}

void setFrequency(uint32_t f) {
  if (f < 1) f = 1;
  if (f > MAX_FREQUENCY_HZ) f = MAX_FREQUENCY_HZ;

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);
  if (halfBitUs < 1) halfBitUs = 1;

  Serial.print("RX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}
