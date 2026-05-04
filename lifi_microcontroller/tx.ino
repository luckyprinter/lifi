// Arduino_TX.ino
#define TX_PIN           8
#define BIT_DURATION_MS  80      // Keep around 80-100ms for stability

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);     // LED ON when idle
  Serial.println("TX Ready");
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() == 0) return;

    // Preamble
    for (int i = 0; i < 4; i++) {
      sendByte(0xAA);
      delay(30);
    }

    sendByte(input.length());

    for (char c : input) {
      sendByte((uint8_t)c);
    }

    uint8_t checksum = 0;
    for (char c : input) checksum += (uint8_t)c;
    sendByte(checksum);

    Serial.println("Sent");
  }
}

void sendByte(uint8_t val) {
  for (int i = 7; i >= 0; i--) {
    bool bit = (val & (1 << i)) != 0;
    digitalWrite(TX_PIN, bit ? HIGH : LOW);
    delay(BIT_DURATION_MS);
  }
}