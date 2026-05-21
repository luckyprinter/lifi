#include "driver/gpio.h"

#define TX_PIN 5

const uint8_t PREAMBLE_BYTE = 0x55;
const uint8_t START_BYTE = 0x02;
const uint8_t STOP_BYTE = 0x03;
const uint8_t TYPE_TEXT = 0x01;

const uint8_t PREAMBLE_COUNT = 12;
const uint16_t MAX_TEXT_LEN = 240;
const uint32_t MIN_FREQUENCY_HZ = 1;
const uint32_t MAX_FREQUENCY_HZ = 15000;

uint32_t frequencyHz = 1000;
uint32_t halfBitUs = 500;

// Change this if the physical TX driver inverts the ESP32 pin.
// false: GPIO HIGH = light ON, GPIO LOW = light OFF.
// true:  GPIO LOW = light ON, GPIO HIGH = light OFF.
bool txInverted = false;

void setLight(bool on) {
  bool level = txInverted ? !on : on;
  gpio_set_level((gpio_num_t)TX_PIN, level ? 1 : 0);
}

void setup() {
#if defined(ARDUINO_ARCH_ESP32)
  Serial.setRxBufferSize(4096);
#endif

  Serial.begin(115200);
  Serial.setTimeout(50);

  pinMode(TX_PIN, OUTPUT);
  setLight(false);
  setFrequency(frequencyHz);

  Serial.println("TX_TEXT_DEBUG_READY");
  Serial.println("COMMANDS:FREQ=1000,INV=0,SEND=hello,RAW=55,LED=1,LED=0,STATUS");
}

void loop() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  if (line.startsWith("FREQ=")) {
    setFrequency((uint32_t)line.substring(5).toInt());
    return;
  }

  if (line.startsWith("INV=")) {
    txInverted = line.substring(4).toInt() != 0;
    Serial.print("TX_INV=");
    Serial.println(txInverted ? 1 : 0);
    setLight(false);
    return;
  }

  if (line.startsWith("LED=")) {
    bool on = line.substring(4).toInt() != 0;
    setLight(on);
    Serial.print("TX_LED=");
    Serial.println(on ? "ON" : "OFF");
    return;
  }

  if (line == "STATUS") {
    printStatus();
    return;
  }

  if (line.startsWith("RAW=")) {
    uint8_t value = (uint8_t)strtoul(line.substring(4).c_str(), nullptr, 16);
    uint32_t deadline = micros();
    sendManchesterByte(value, deadline, true);
    setLight(false);
    Serial.print("TX_RAW_SENT:0x");
    printHex2(value);
    Serial.println();
    return;
  }

  if (line.startsWith("SEND=")) {
    sendTextPacket(line.substring(5));
    return;
  }

  Serial.print("TX_UNKNOWN:");
  Serial.println(line);
}

void setFrequency(uint32_t f) {
  if (f < MIN_FREQUENCY_HZ) f = MIN_FREQUENCY_HZ;
  if (f > MAX_FREQUENCY_HZ) f = MAX_FREQUENCY_HZ;

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);
  if (halfBitUs < 1) halfBitUs = 1;

  Serial.print("TX_FREQ:");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.println(halfBitUs);
}

void printStatus() {
  Serial.print("TX_STATUS:freq=");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.print(halfBitUs);
  Serial.print(":inv=");
  Serial.println(txInverted ? 1 : 0);
}

uint16_t crc16Update(uint16_t crc, uint8_t data) {
  crc ^= (uint16_t)data << 8;
  for (uint8_t i = 0; i < 8; i++) {
    if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
    else crc <<= 1;
  }
  return crc & 0xFFFF;
}

uint16_t packetCrc(uint8_t type, uint16_t len, const uint8_t *payload) {
  uint16_t crc = 0xFFFF;
  crc = crc16Update(crc, type);
  crc = crc16Update(crc, (len >> 8) & 0xFF);
  crc = crc16Update(crc, len & 0xFF);
  for (uint16_t i = 0; i < len; i++) crc = crc16Update(crc, payload[i]);
  return crc;
}

void sendTextPacket(String text) {
  if (text.length() > MAX_TEXT_LEN) {
    text = text.substring(0, MAX_TEXT_LEN);
    Serial.print("TX_WARN:truncated_to=");
    Serial.println(MAX_TEXT_LEN);
  }

  uint16_t len = (uint16_t)text.length();
  const uint8_t *payload = (const uint8_t *)text.c_str();
  uint16_t crc = packetCrc(TYPE_TEXT, len, payload);
  uint32_t deadline = micros();

  Serial.print("TX_PACKET_START:type=1:len=");
  Serial.print(len);
  Serial.print(":crc=0x");
  printHex4(crc);
  Serial.println();

  sendFrameGap();
  deadline = micros();

  for (uint8_t i = 0; i < PREAMBLE_COUNT; i++) {
    sendManchesterByte(PREAMBLE_BYTE, deadline, false);
  }

  sendManchesterByte(START_BYTE, deadline, false);
  sendManchesterByte(TYPE_TEXT, deadline, false);
  sendManchesterByte((len >> 8) & 0xFF, deadline, false);
  sendManchesterByte(len & 0xFF, deadline, false);

  for (uint16_t i = 0; i < len; i++) {
    sendManchesterByte(payload[i], deadline, false);
  }

  sendManchesterByte((crc >> 8) & 0xFF, deadline, false);
  sendManchesterByte(crc & 0xFF, deadline, false);
  sendManchesterByte(STOP_BYTE, deadline, false);

  setLight(false);

  Serial.print("TX_PACKET_DONE:type=1:len=");
  Serial.print(len);
  Serial.print(":crc=0x");
  printHex4(crc);
  Serial.println();
}

void sendFrameGap() {
  setLight(false);
  uint32_t gapUs = halfBitUs * 40;
  if (gapUs < 3000) gapUs = 3000;
  if (gapUs > 20000) gapUs = 20000;
  delayMicroseconds(gapUs);
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

void sendManchesterByte(uint8_t b, uint32_t &deadline, bool verbose) {
  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 0x01;
    setLight(!bit);
    waitNextHalfBit(deadline);
    setLight(bit);
    waitNextHalfBit(deadline);

    if (verbose) {
      Serial.print("TX_BIT:");
      Serial.println(bit ? 1 : 0);
    }
  }
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
