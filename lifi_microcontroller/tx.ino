// TX - Manchester Encoding with frequency control
#define TX_PIN           8

uint32_t frequencyHz = 500;    // default bit frequency in Hz
uint32_t halfBitUs = 1000;    // default half-bit duration in microseconds

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);
  updateTiming();

  Serial.println("\n=== Manchester TX ===");
  Serial.print("Frequency: "); Serial.print(frequencyHz); Serial.println(" Hz");
  Serial.print("Full bit duration: "); Serial.print(halfBitUs * 2.0 / 1000.0); Serial.println(" ms");
  Serial.print("Half bit duration: "); Serial.print(halfBitUs); Serial.println(" us\n");
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
    if (input.startsWith("TIME_MS=")) {
      setBitTime(input.substring(8));
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

void sendManchesterByte(uint8_t byte) {
  digitalWrite(TX_PIN, LOW);
  delayMicroseconds(halfBitUs);
  digitalWrite(TX_PIN, HIGH);
  delayMicroseconds(halfBitUs);

  for (int i = 7; i >= 0; i--) {
    bool bit = (byte & (1 << i)) != 0;
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
