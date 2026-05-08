#define RX_PIN 5
#define SOF 0x7E

uint32_t frequencyHz = 1000;
uint32_t halfBitUs;

enum State {
  WAIT_SOF,
  READ_TYPE,
  READ_SEQ,
  READ_LEN,
  READ_DATA,
  READ_CRC
};

State state = WAIT_SOF;

uint8_t type, seq, len, idx;
uint8_t buffer[64];
uint8_t crc;

String message = "";

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);

  setFrequency(frequencyHz);
  Serial.println("RX Ready");
}

void loop() {
  uint8_t byte = readByte();

  switch (state) {

    case WAIT_SOF:
      if (byte == SOF) state = READ_TYPE;
      break;

    case READ_TYPE:
      type = byte;
      state = READ_SEQ;
      break;

    case READ_SEQ:
      seq = byte;
      state = READ_LEN;
      break;

    case READ_LEN:
      len = byte;
      idx = 0;
      crc = 0;
      state = READ_DATA;
      break;

    case READ_DATA:
      buffer[idx++] = byte;
      crc ^= byte;

      if (idx >= len) {
        state = READ_CRC;
      }
      break;

    case READ_CRC:
      if (crc == byte) {
        // valid packet
        for (int i = 0; i < len; i++) {
          message += (char)buffer[i];
        }

        Serial.print("RX OK: ");
        Serial.println(message);
      } else {
        Serial.println("CRC FAIL");
      }

      message = "";
      state = WAIT_SOF;
      break;
  }
}

// ---------------- MANCHESTER RX ----------------

uint8_t readByte() {
  uint8_t value = 0;

  // sync
  while (digitalRead(RX_PIN) == HIGH);
  while (digitalRead(RX_PIN) == LOW);

  delayMicroseconds(halfBitUs / 2);

  for (int i = 7; i >= 0; i--) {
    delayMicroseconds(halfBitUs);
    bool first = digitalRead(RX_PIN);

    delayMicroseconds(halfBitUs);
    bool second = digitalRead(RX_PIN);

    if (first == second) return 0; // invalid

    if (second) value |= (1 << i);
  }

  return value;
}

void setFrequency(uint32_t f) {
  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("RX freq: ");
  Serial.println(frequencyHz);
}