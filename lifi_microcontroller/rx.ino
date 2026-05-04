// ESP32_RX.ino
#define RX_PIN 5
#define BIT_DURATION_MS 80

String buffer = "";
unsigned long lastPacket = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);
  Serial.println("RX Ready");
}

void loop() {
  static bool wasHigh = true;
  bool current = digitalRead(RX_PIN);

  if (current != wasHigh) {
    wasHigh = current;
    if (current == LOW) {
      delay(BIT_DURATION_MS / 2 + 25);

      uint8_t value = 0;
      for (int i = 7; i >= 0; i--) {
        int count = 0;
        for (int s = 0; s < 4; s++) {
          delay(BIT_DURATION_MS / 4);
          if (digitalRead(RX_PIN)) count++;
        }
        if (count >= 2) value |= (1 << i);
      }

      buffer += (char)value;
      lastPacket = millis();
    }
  }

  if (buffer.length() > 0 && (millis() - lastPacket > 2500)) {
    Serial.println(buffer);
    buffer = "";
  }
}