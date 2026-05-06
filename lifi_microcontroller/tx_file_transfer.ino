// TX - Arduino UNO Manchester File Transfer
// Compatible with raw binary file transfer over serial-to-light using 1kHz-style Manchester timing.

#define TX_PIN 8

uint32_t frequencyHz = 500;
uint32_t halfBitUs;

void setup() {
  Serial.begin(115200);
  pinMode(TX_PIN, OUTPUT);
  digitalWrite(TX_PIN, LOW);

  setFrequency(frequencyHz);
  Serial.println("TX File Transfer Ready");
}

void loop() {
  if (!Serial.available()) {
    return;
  }

  int peeked = Serial.peek();
  if (peeked == 'F') {
    handleCommand();
    return;
  }

  if (peeked == 0x02) {
    if (Serial.available() < 3) {
      return; // wait until full transfer header is available
    }
    Serial.read(); // consume START byte
    uint16_t size = (uint16_t)Serial.read() << 8;
    size |= (uint16_t)Serial.read();

    sendManchesterByte(0x02);
    sendManchesterByte((size >> 8) & 0xFF);
    sendManchesterByte(size & 0xFF);

    for (uint16_t remaining = size; remaining > 0; remaining--) {
      while (!Serial.available()) {
        // wait for serial data
      }
      sendManchesterByte((uint8_t)Serial.read());
    }

    Serial.println("TX: file stream sent");
    return;
  }

  // Normal byte-by-byte Manchester transmission
  uint8_t b = (uint8_t)Serial.read();
  sendManchesterByte(b);
}

void handleCommand() {
  String line = Serial.readStringUntil('\n');
  line.trim();

  if (line.startsWith("FREQ=")) {
    uint32_t newFreq = line.substring(5).toInt();
    setFrequency(newFreq);
    return;
  }

  // Unknown command is ignored while preserving stability
  Serial.print("TX: unknown command ");
  Serial.println(line);
}

void setFrequency(uint32_t f) {
  if (f == 0) {
    return;
  }

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("TX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}

void sendManchesterByte(uint8_t b) {
  digitalWrite(TX_PIN, LOW);
  delayMicroseconds(halfBitUs);
  digitalWrite(TX_PIN, HIGH);
  delayMicroseconds(halfBitUs);

  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 0x01;
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
