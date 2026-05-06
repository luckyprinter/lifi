// RX - Manchester Decoding
#define RX_PIN              5

uint16_t halfBitMs = 1;      // default half-bit delay in milliseconds

String messageBuffer = "";
unsigned long lastCharTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);
  Serial.println("\n=== Manchester Receiver Ready ===");
  printCurrentTiming();
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0) {
      if (input.startsWith("FREQ=")) {
        setFrequency(input.substring(5));
      }
    }
  }

  // Wait for start bit transition (Low -> High)
  while (digitalRead(RX_PIN) == HIGH) delay(1);
  while (digitalRead(RX_PIN) == LOW) delay(1);

  delay(halfBitMs / 2);

  uint8_t value = 0;

  for (int i = 7; i >= 0; i--) {
    delay(halfBitMs);
    bool firstHalf = digitalRead(RX_PIN);

    delay(halfBitMs);
    bool secondHalf = digitalRead(RX_PIN);

    bool bit = secondHalf;   // In Manchester, second half is the actual bit value

    if (firstHalf == secondHalf) {
      Serial.println("[ERROR] No transition - invalid Manchester bit");
      return;
    }

    if (bit) value |= (1 << i);
  }

  char ch = (char)value;
  messageBuffer += ch;
  lastCharTime = millis();

  Serial.printf("Received: '%c' (0x%02X)\n", ch, value);

  if (messageBuffer.length() > 0 && (millis() - lastCharTime > 1500)) {
    Serial.println("\n=== MESSAGE COMPLETE ===");
    Serial.print("Full message: \"");
    Serial.print(messageBuffer);
    Serial.println("\"\n");
    messageBuffer = "";
  }
}

void setFrequency(const String &arg) {
  uint32_t newFreq = (uint32_t)arg.toInt();
  if (newFreq == 0) {
    Serial.println("[ERROR] Invalid frequency");
    return;
  }
  
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
