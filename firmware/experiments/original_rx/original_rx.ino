// ESP32 RX - Manchester Decoding
#define RX_PIN              5
#define HALF_BIT_MS         1      // Must match TX BIT_DURATION_MS

String messageBuffer = "";
unsigned long lastCharTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);
  Serial.println("\n=== ESP32 Manchester Receiver Ready ===\n");
}

void loop() {
  // Wait for start bit transition (Low -> High)
  while (digitalRead(RX_PIN) == HIGH) delay(1);   // wait for LOW
  while (digitalRead(RX_PIN) == LOW) delay(1);    // wait for rising edge

  delay(HALF_BIT_MS / 2);   // go to middle of first half-bit

  uint8_t value = 0;

  for (int i = 7; i >= 0; i--) {     // MSB first
    // Sample at middle of bit
    delay(HALF_BIT_MS);
    bool firstHalf = digitalRead(RX_PIN);

    delay(HALF_BIT_MS);
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