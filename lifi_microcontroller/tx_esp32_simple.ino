// ESP32 TX - Manchester Encoding (Simple Text Version)
#define TX_PIN            5    // Choose a safe ESP32 GPIO pin
#define HALF_BIT_US       1000 // Must match RX half-bit timing (500 Hz = 1 ms)
#define INTER_BYTE_US     2000 // Delay between bytes to avoid receiver overload
#define LINE_BUFFER_SIZE  512

char lineBuffer[LINE_BUFFER_SIZE];
size_t lineLength = 0;

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);

  Serial.println("\n=== ESP32 Manchester TX (Simple) ===");
  Serial.print("Half bit: ");
  Serial.print(HALF_BIT_US);
  Serial.println(" us\n");
}

void loop() {
  while (Serial.available()) {
    int c = Serial.read();
    if (c < 0) {
      break;
    }

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      if (lineLength == 0) {
        continue;
      }

      sendManchesterMessage((uint8_t*)lineBuffer, lineLength);
      lineLength = 0;
      continue;
    }

    if (lineLength < LINE_BUFFER_SIZE - 1) {
      lineBuffer[lineLength++] = (char)c;
    }
  }
}

void sendManchesterMessage(const uint8_t* data, size_t length) {
  Serial.print("Sending ");
  Serial.print(length);
  Serial.println(" bytes...");

  for (size_t i = 0; i < length; i++) {
    sendManchesterByte(data[i]);
    delayMicroseconds(INTER_BYTE_US);
  }

  Serial.println("--- Message sent ---\n");
}

void sendManchesterByte(uint8_t byte) {
  digitalWrite(TX_PIN, LOW);
  delayMicroseconds(HALF_BIT_US);
  digitalWrite(TX_PIN, HIGH);
  delayMicroseconds(HALF_BIT_US);

  for (int i = 7; i >= 0; i--) {
    bool bit = (byte & (1 << i)) != 0;
    digitalWrite(TX_PIN, !bit);
    delayMicroseconds(HALF_BIT_US);
    digitalWrite(TX_PIN, bit);
    delayMicroseconds(HALF_BIT_US);
  }

  digitalWrite(TX_PIN, HIGH);
  delayMicroseconds(HALF_BIT_US);
  digitalWrite(TX_PIN, LOW);
  delayMicroseconds(HALF_BIT_US);
}