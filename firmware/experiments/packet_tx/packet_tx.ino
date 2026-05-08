// ================= TX PACKET MANCHESTER =================
#define TX_PIN 8
#define SOF 0x7E

uint32_t frequencyHz = 1000;
uint32_t halfBitUs;

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);

  setFrequency(frequencyHz);
  Serial.println("TX Ready");
}

void loop() {
  if (Serial.available()) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();
    if (msg.length() == 0) return;

    sendText(msg);
  }
}

void setFrequency(uint32_t f) {
  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("Freq set: ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | half-bit ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}

// ---------------- PACKET SENDER ----------------

void sendText(String msg) {
  uint8_t seq = 0;

  for (int i = 0; i < msg.length(); i += 16) {
    uint8_t len = min(16, (int)msg.length() - i);

    uint8_t crc = 0;

    sendByte(SOF);
    sendByte('T');
    sendByte(seq++);
    sendByte(len);

    for (int j = 0; j < len; j++) {
      uint8_t b = msg[i + j];
      sendByte(b);
      crc ^= b;
    }

    sendByte(crc);

    delay(5); // small gap between packets
  }
}

// ---------------- MANCHESTER TX ----------------

void sendByte(uint8_t b) {
  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 1;

    digitalWrite(TX_PIN, !bit);
    delayMicroseconds(halfBitUs);

    digitalWrite(TX_PIN, bit);
    delayMicroseconds(halfBitUs);
  }
}