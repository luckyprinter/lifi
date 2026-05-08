// RX - ESP32 Manchester Decoder (µs stable)
#define RX_PIN 5

uint32_t frequencyHz = 500;
uint32_t halfBitUs;

String buffer = "";

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);

  setFrequency(frequencyHz);
  Serial.println("RX Ready");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("FREQ=")) {
      setFrequency(cmd.substring(5).toInt());
    }
  }

  // --- SYNC PHASE ---
  while (digitalRead(RX_PIN) == HIGH);
  while (digitalRead(RX_PIN) == LOW);

  delayMicroseconds(halfBitUs / 2);

  uint8_t value = 0;

  for (int i = 7; i >= 0; i--) {

    delayMicroseconds(halfBitUs);
    bool first = digitalRead(RX_PIN);

    delayMicroseconds(halfBitUs);
    bool second = digitalRead(RX_PIN);

    // relaxed validation (important for ESP32 jitter tolerance)
    if (first == second) {
      Serial.println("[WARN] Bit unstable");
      return;
    }

    bool bit = second;
    if (bit) value |= (1 << i);
  }

  char c = (char)value;
  buffer += c;

  Serial.print("RX: ");
  Serial.println(c);
}

void setFrequency(uint32_t f) {
  if (f == 0) return;

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("RX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}