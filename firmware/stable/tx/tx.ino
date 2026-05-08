// TX - Arduino UNO (Stable µs Manchester TX)
#define TX_PIN 8

uint32_t frequencyHz = 500;
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
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() == 0) return;

    if (input.startsWith("FREQ=")) {
      setFrequency(input.substring(5).toInt());
      return;
    }

    for (char c : input) {
      sendManchesterByte((uint8_t)c);
      delay(120);
    }
  }
}

void setFrequency(uint32_t f) {
  if (f == 0) return;

  frequencyHz = f;

  // deterministic integer math
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("TX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}

void sendManchesterByte(uint8_t b) {
  digitalWrite(TX_PIN, LOW);
  delayMicroseconds(halfBitUs);
  digitalWrite(TX_PIN, HIGH);
  delayMicroseconds(halfBitUs);

  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 1;

    digitalWrite(TX_PIN, !bit);
    delayMicroseconds(halfBitUs);

    digitalWrite(TX_PIN, bit);
    delayMicroseconds(halfBitUs);
  }

  digitalWrite(TX_PIN, HIGH);
  delayMicroseconds(halfBitUs);

  digitalWrite(TX_PIN, LOW);
  delayMicroseconds(halfBitUs);
}