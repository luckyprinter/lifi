#include "driver/gpio.h"

#define TX_PIN 5

const uint8_t SOF = 0x7E;
const uint8_t TYPE_END = 0x00;
const uint8_t TYPE_TEXT = 0x01;
const uint8_t TYPE_IMAGE = 0x02;
const uint8_t TYPE_AUDIO = 0x03;

const uint32_t MAX_FREQUENCY_HZ = 50000;
const uint8_t MAX_PAYLOAD_LEN = 48;

uint32_t frequencyHz = 9000;
uint32_t halfBitUs = 55;
uint8_t currentType = TYPE_TEXT;
bool byteSyncGuard = true;

inline void txLightOn() {
  gpio_set_level((gpio_num_t)TX_PIN, 1);
}

inline void txLightOff() {
  gpio_set_level((gpio_num_t)TX_PIN, 0);
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);

  pinMode(TX_PIN, OUTPUT);
  txLightOn();

  setFrequency(frequencyHz);
  Serial.println("PACKET_CRC_TX_READY:active_high_mosfet:type_1_text");
}

void loop() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  if (line.startsWith("FREQ=")) {
    setFrequency(line.substring(5).toInt());
    return;
  }

  if (line.startsWith("TYPE=")) {
    uint8_t requested = (uint8_t)line.substring(5).toInt();
    if (requested >= TYPE_TEXT && requested <= TYPE_AUDIO) {
      currentType = requested;
      Serial.print("TX_TYPE=");
      Serial.println(currentType);
    } else {
      Serial.println("TX_ERROR:type must be 1 text, 2 image, or 3 audio");
    }
    return;
  }

  if (line.startsWith("GUARD=")) {
    byteSyncGuard = (line.substring(6).toInt() != 0);
    Serial.print("TX_GUARD=");
    Serial.println(byteSyncGuard ? 1 : 0);
    return;
  }

  if (line == "END") {
    sendPacket(TYPE_END, 0, nullptr, 0);
    Serial.println("TX_PACKET_END_SENT");
    return;
  }

  if (line.startsWith("SEND=")) {
    sendText(line.substring(5));
    return;
  }

  sendText(line);
}

void sendText(const String &msg) {
  uint8_t seq = 0;

  for (uint16_t offset = 0; offset < msg.length(); offset += MAX_PAYLOAD_LEN) {
    uint8_t len = min((uint16_t)MAX_PAYLOAD_LEN, (uint16_t)(msg.length() - offset));
    uint8_t payload[MAX_PAYLOAD_LEN];

    for (uint8_t i = 0; i < len; i++) {
      payload[i] = (uint8_t)msg[offset + i];
    }

    sendPacket(currentType, seq++, payload, len);
    delay(5);
  }

  sendPacket(TYPE_END, seq, nullptr, 0);
  txLightOn();

  Serial.print("TX_PACKET_MESSAGE_SENT:type=");
  Serial.print(currentType);
  Serial.print(":bytes=");
  Serial.println(msg.length());
}

void sendPacket(uint8_t type, uint8_t seq, const uint8_t *payload, uint8_t len) {
  uint8_t crc = type ^ seq ^ len;
  for (uint8_t i = 0; i < len; i++) {
    crc ^= payload[i];
  }

  sendByte(SOF);
  sendByte(type);
  sendByte(seq);
  sendByte(len);
  for (uint8_t i = 0; i < len; i++) {
    sendByte(payload[i]);
  }
  sendByte(crc);

  Serial.print("TX_PACKET_SENT:type=");
  Serial.print(type);
  Serial.print(":seq=");
  Serial.print(seq);
  Serial.print(":len=");
  Serial.print(len);
  Serial.print(":crc=0x");
  if (crc < 16) Serial.print("0");
  Serial.println(crc, HEX);
}

void sendByte(uint8_t b) {
  if (byteSyncGuard) {
    // Legacy-compatible byte sync used by the old working carousel TX:
    // idle light is ON, then one OFF/ON Manchester cell marks the byte start.
    txLightOff();
    delayMicroseconds(halfBitUs);
    txLightOn();
    delayMicroseconds(halfBitUs);
  }

  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 1;

    if (!bit) txLightOn();
    else txLightOff();
    delayMicroseconds(halfBitUs);

    if (bit) txLightOn();
    else txLightOff();
    delayMicroseconds(halfBitUs);
  }

  txLightOn();
  delayMicroseconds(halfBitUs);
}

void setFrequency(uint32_t f) {
  if (f < 1) f = 1;
  if (f > MAX_FREQUENCY_HZ) f = MAX_FREQUENCY_HZ;

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);
  if (halfBitUs < 1) halfBitUs = 1;

  Serial.print("TX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}
