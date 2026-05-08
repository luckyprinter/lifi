#define RX_PIN 5
#define START_BYTE 0x02

uint32_t frequencyHz = 1000;
uint32_t halfBitUs;

bool receiving = false;
uint16_t imgSize = 0;
uint16_t index = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);

  setFrequency(frequencyHz);
  Serial.println("RX Ready (File Transfer v1)");
}

void loop() {
  uint8_t b = readByte();

  if (!receiving) {
    if (b == START_BYTE) {
      receiving = true;

      uint8_t high = readByte();
      uint8_t low = readByte();

      imgSize = (high << 8) | low;
      index = 0;

      Serial.println("RX: Image start");
    }
  } 
  else {
    Serial.write(b); // stream to PC

    index++;

    if (index >= imgSize) {
      receiving = false;
      Serial.println("\nRX: Image complete");
    }
  }
}

// ---------------- MANCHESTER RX ----------------

uint8_t readByte() {
  uint8_t value = 0;

  while (digitalRead(RX_PIN) == HIGH);
  while (digitalRead(RX_PIN) == LOW);

  delayMicroseconds(halfBitUs / 2);

  for (int i = 7; i >= 0; i--) {
    delayMicroseconds(halfBitUs);
    bool a = digitalRead(RX_PIN);

    delayMicroseconds(halfBitUs);
    bool b = digitalRead(RX_PIN);

    if (a == b) return 0;

    if (b) value |= (1 << i);
  }

  return value;
}

void setFrequency(uint32_t f) {
  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);
}