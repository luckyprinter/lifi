// TX - Manchester Encoding
#define TX_PIN           8

uint16_t halfBitMs = 1;      // default half-bit delay in milliseconds

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);

  Serial.println("\n=== Manchester TX ===");
  printCurrentTiming();
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() == 0) return;

    if (input.startsWith("FREQ=")) {
      setFrequency(input.substring(5));
      return;
    }

    Serial.print("Sending: \""); Serial.print(input); Serial.println("\"");

    for (char c : input) {
      sendManchesterByte((uint8_t)c);
      delay(120);
    }
    Serial.println("--- Message sent ---\n");
  }
}

void setFrequency(const String &arg) {
  uint32_t newFreq = (uint32_t)arg.toInt();
  if (newFreq == 0) {
    Serial.println("[ERROR] Invalid frequency");
    return;
  }
  
  // Calculate half-bit delay from frequency
  // frequency = 1 / (fullBitTime), fullBitTime = 2 * halfBitTime
  // So: halfBitMs = 1000 / (2 * frequency)
  uint16_t calcHalfBitMs = (uint16_t)(500.0f / newFreq + 0.5f);
  if (calcHalfBitMs == 0) calcHalfBitMs = 1;
  
  halfBitMs = calcHalfBitMs;
  Serial.print("[OK] Frequency set to: "); Serial.print(newFreq); Serial.println(" Hz");
  printCurrentTiming();
}

void printCurrentTiming() {
  float fullBitMs = halfBitMs * 2.0f;
  float frequencyHz = 1000.0f / fullBitMs;
  Serial.print("Full bit: "); Serial.print(fullBitMs); Serial.println(" ms");
  Serial.print("Half bit: "); Serial.print(halfBitMs); Serial.println(" ms");
  Serial.print("Frequency: "); Serial.print((uint32_t)frequencyHz); Serial.println(" Hz\n");
}

void sendManchesterByte(uint8_t byte) {
  // Start bit: Low -> High
  digitalWrite(TX_PIN, LOW);
  delay(halfBitMs);
  digitalWrite(TX_PIN, HIGH);
  delay(halfBitMs);

  for (int i = 7; i >= 0; i--) {
    bool bit = (byte & (1 << i)) != 0;
    digitalWrite(TX_PIN, !bit);
    delay(halfBitMs);
    digitalWrite(TX_PIN, bit);
    delay(halfBitMs);
  }

  // Stop bit: High -> Low
  digitalWrite(TX_PIN, HIGH);
  delay(halfBitMs);
  digitalWrite(TX_PIN, LOW);
  delay(halfBitMs);
}
