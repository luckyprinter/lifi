// RX - Manchester Decoding with frequency control
#define RX_PIN              5

uint32_t frequencyHz = 500;
uint32_t halfBitUs = 1000;

String messageBuffer = "";
unsigned long lastCharTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);
  updateTiming();
  Serial.println("\n=== Manchester Receiver Ready ===\n");
  Serial.print("Frequency: "); Serial.print(frequencyHz); Serial.println(" Hz");
  Serial.print("Full bit duration: "); Serial.print(halfBitUs * 2.0 / 1000.0); Serial.println(" ms");
  Serial.print("Half bit duration: "); Serial.print(halfBitUs); Serial.println(" us\n");
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0) {
      if (input.startsWith("FREQ=")) {
        setFrequency(input.substring(5));
      } else if (input.startsWith("TIME_MS=")) {
        setBitTime(input.substring(8));
      }
    }
  }

  while (digitalRead(RX_PIN) == HIGH) delay(1);
  while (digitalRead(RX_PIN) == LOW) delay(1);

  delayMicroseconds(halfBitUs / 2);

  uint8_t value = 0;

  for (int i = 7; i >= 0; i--) {
    delayMicroseconds(halfBitUs);
    bool firstHalf = digitalRead(RX_PIN);
    delayMicroseconds(halfBitUs);
    bool secondHalf = digitalRead(RX_PIN);

    if (firstHalf == secondHalf) {
      Serial.println("[ERROR] No transition - invalid Manchester bit");
      return;
    }

    bool bit = secondHalf;
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
  frequencyHz = newFreq;
  updateTiming();
  Serial.print("Frequency set to: "); Serial.print(frequencyHz); Serial.println(" Hz");
  Serial.print("Full bit duration: "); Serial.print(halfBitUs * 2.0 / 1000.0); Serial.println(" ms");
  Serial.print("Half bit duration: "); Serial.print(halfBitUs); Serial.println(" us\n");
}

void setBitTime(const String &arg) {
  float bitTimeMs = arg.toFloat();
  if (bitTimeMs <= 0.0f) {
    Serial.println("[ERROR] Invalid bit time");
    return;
  }
  frequencyHz = (uint32_t)(1000.0f / bitTimeMs + 0.5f);
  halfBitUs = (uint32_t)(bitTimeMs * 500.0f + 0.5f);
  Serial.print("Bit time set to: "); Serial.print(bitTimeMs); Serial.println(" ms");
  Serial.print("Frequency: "); Serial.print(frequencyHz); Serial.println(" Hz");
  Serial.print("Half bit duration: "); Serial.print(halfBitUs); Serial.println(" us\n");
}

void updateTiming() {
  if (frequencyHz == 0) frequencyHz = 1;
  float fullBitUs = 1000000.0f / frequencyHz;
  halfBitUs = (uint32_t)(fullBitUs / 2.0f + 0.5f);
}
