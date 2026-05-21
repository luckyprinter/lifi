#define TX_PIN 8
#define START_BYTE 0x02

uint32_t frequencyHz = 1000;
uint32_t halfBitUs;

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);

  setFrequency(frequencyHz);
  Serial.println("TX Ready (File Transfer v1)");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "SEND_IMAGE") {
      sendImage();
      return;
    }

    sendText(cmd);
  }
}

// ---------------- TEXT ----------------

void sendText(String msg) {
  for (char c : msg) {
    sendByte((uint8_t)c);
  }
}

// ---------------- IMAGE MODE ----------------

void sendImage() {
  Serial.println("TX: Waiting image stream...");

  // read size (2 bytes)
  while (!Serial.available());
  uint8_t high = Serial.read();
  while (!Serial.available());
  uint8_t low = Serial.read();

  uint16_t size = (high << 8) | low;

  // send start
  sendByte(START_BYTE);

  // send size
  sendByte(high);
  sendByte(low);

  // stream data
  for (uint16_t i = 0; i < size; i++) {
    while (!Serial.available());
    uint8_t b = Serial.read();
    sendByte(b);
  }

  Serial.println("TX: Image sent");
}

// ---------------- MANCHESTER ----------------

void setFrequency(uint32_t f) {
  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);
}

void sendByte(uint8_t b) {
  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 1;

    digitalWrite(TX_PIN, !bit);
    delayMicroseconds(halfBitUs);

    digitalWrite(TX_PIN, bit);
    delayMicroseconds(halfBitUs);
  }
}
