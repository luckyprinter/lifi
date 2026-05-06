// RX - ESP32 Manchester File Transfer Receiver
// Reconstructs raw binary stream from Manchester-encoded optical link.

#define RX_PIN 5

uint32_t frequencyHz = 1000;
uint32_t halfBitUs;

enum RxState {
  WAIT_START,
  READ_SIZE_MSB,
  READ_SIZE_LSB,
  READ_DATA
};

RxState rxState = WAIT_START;
uint16_t expectedSize = 0;
uint16_t bytesRemaining = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RX_PIN, INPUT);

  setFrequency(frequencyHz);
  Serial.println("RX File Transfer Ready");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("FREQ=")) {
      setFrequency(cmd.substring(5).toInt());
    }
  }

  int received = receiveManchesterByte();
  if (received < 0) {
    return;
  }

  uint8_t data = (uint8_t)received;
  processReceivedByte(data);
}

int receiveManchesterByte() {
  while (digitalRead(RX_PIN) == HIGH);
  while (digitalRead(RX_PIN) == LOW);
  delayMicroseconds(halfBitUs / 2);

  uint8_t value = 0;
  for (int i = 7; i >= 0; i--) {
    delayMicroseconds(halfBitUs);
    bool first = digitalRead(RX_PIN);
    delayMicroseconds(halfBitUs);
    bool second = digitalRead(RX_PIN);

    if (first == second) {
      return -1;
    }

    bool bit = second;
    if (bit) {
      value |= (1 << i);
    }
  }

  return value;
}

void processReceivedByte(uint8_t data) {
  switch (rxState) {
    case WAIT_START:
      if (data == 0x02) {
        rxState = READ_SIZE_MSB;
      }
      break;

    case READ_SIZE_MSB:
      expectedSize = ((uint16_t)data) << 8;
      rxState = READ_SIZE_LSB;
      break;

    case READ_SIZE_LSB:
      expectedSize |= data;
      bytesRemaining = expectedSize;
      if (expectedSize == 0) {
        Serial.println("[RX] empty transfer, done");
        rxState = WAIT_START;
      } else {
        Serial.print("[RX] receiving ");
        Serial.print(expectedSize);
        Serial.println(" bytes");
        rxState = READ_DATA;
      }
      break;

    case READ_DATA:
      Serial.write(data);
      if (bytesRemaining > 0) {
        bytesRemaining--;
      }
      if (bytesRemaining == 0) {
        Serial.println();
        Serial.println("[RX] FILE_TRANSFER_COMPLETE");
        rxState = WAIT_START;
      }
      break;
  }
}

void setFrequency(uint32_t f) {
  if (f == 0) {
    return;
  }

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  Serial.print("RX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}
