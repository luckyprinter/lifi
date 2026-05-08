// TX - Manchester Encoding
#define TX_PIN           8
#define HALF_BIT_MS      1      // Must match RX

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);

  Serial.println("\n=== Manchester TX ===");
  Serial.print("Full bit duration: "); Serial.print(HALF_BIT_MS*2); Serial.println(" ms\n");
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() == 0) return;

    Serial.print("Sending: \""); Serial.print(input); Serial.println("\"");

    for (char c : input) {
      sendManchesterByte((uint8_t)c);
      delay(120);
    }
    Serial.println("--- Message sent ---\n");
  }
}

void sendManchesterByte(uint8_t byte) {
  // Start bit: Low -> High
  digitalWrite(TX_PIN, LOW);
  delay(HALF_BIT_MS);
  digitalWrite(TX_PIN, HIGH);
  delay(HALF_BIT_MS);

  for (int i = 7; i >= 0; i--) {
    bool bit = (byte & (1 << i)) != 0;
    digitalWrite(TX_PIN, !bit);
    delay(HALF_BIT_MS);
    digitalWrite(TX_PIN, bit);
    delay(HALF_BIT_MS);
  }

  // Stop bit: High -> Low
  digitalWrite(TX_PIN, HIGH);
  delay(HALF_BIT_MS);
  digitalWrite(TX_PIN, LOW);
  delay(HALF_BIT_MS);
}/