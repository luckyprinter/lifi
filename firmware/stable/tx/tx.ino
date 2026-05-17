#include <Arduino.h>
#if __has_include(<esp_arduino_version.h>)
#include <esp_arduino_version.h>
#endif

#define TX_PIN 5

const uint8_t START_BYTE = 0x02;
const uint8_t PREAMBLE_BYTE = 0xAA;
const uint8_t TYPE_CAROUSEL_CHUNK = 0x20;
const uint8_t TYPE_CAROUSEL_PARITY = 0x21;

const uint8_t PREAMBLE_COUNT = 32;
const uint32_t MAX_FREQUENCY_HZ = 50000;
const uint32_t FRAME_GAP_US = 0;
const uint16_t QUIET_PROGRESS_EVERY_FRAMES = 32;

// DC-biased PWM optical modulation settings.
//
// The LED is no longer switched fully ON/OFF for Manchester symbols.
// Instead, every optical symbol is sent as either bright or dim light.
// Keeping a strong DC light level reduces visible brightness pumping and
// eye strain, while the phototransistor still sees the high-speed changes.
//
// 40 kHz PWM is far above the 9 kHz LiFi data frequency. The LED therefore
// looks mostly steady to human eyes, while the RX phototransistor still sees
// the slower Manchester bright/dim envelope.
const uint32_t PWM_FREQ_HZ = 40000;
const uint8_t PWM_RESOLUTION_BITS = 8;
const uint8_t PWM_CHANNEL = 0;
const uint32_t PWM_MAX_DUTY = (1UL << PWM_RESOLUTION_BITS) - 1;

// Your current IRLZ44N gate drive is assumed active-high:
// GPIO HIGH -> MOSFET ON -> LED brighter.
// If your actual wiring still behaves as active-low, change this to true.
const bool LED_ACTIVE_LOW = false;

// Start with a moderate 96% vs 76% optical difference. This is gentler than
// 100/70, but still gives the simple phototransistor RX a practical 20%
// optical contrast for reliable 9 kHz image/audio transfer.
//
// Idle is set to the average of bright/dim states: (96 + 76) / 2 = 86.
// Matching idle brightness to the average transmission brightness reduces
// low-frequency envelope flicker at chunk/frame boundaries, round gaps, and
// txIdle() transitions.
const uint8_t LED_IDLE_BRIGHTNESS_PERCENT = 86;
const uint8_t LED_BRIGHT_PERCENT = 96;
const uint8_t LED_DIM_PERCENT = 76;

uint32_t frequencyHz = 9000;
uint32_t halfBitUs = 55;
bool quietMode = false;
uint32_t framesSentSinceBoot = 0;

void setupPwmOutput() {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(TX_PIN, PWM_FREQ_HZ, PWM_RESOLUTION_BITS);
#else
  ledcSetup(PWM_CHANNEL, PWM_FREQ_HZ, PWM_RESOLUTION_BITS);
  ledcAttachPin(TX_PIN, PWM_CHANNEL);
#endif
}

void writePwmDuty(uint32_t duty) {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(TX_PIN, duty);
#else
  ledcWrite(PWM_CHANNEL, duty);
#endif
}

void detachPwmOutput() {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcDetach(TX_PIN);
#else
  ledcDetachPin(TX_PIN);
#endif
}

void writeLedDigital(bool ledOn) {
  if (LED_ACTIVE_LOW) {
    digitalWrite(TX_PIN, ledOn ? LOW : HIGH);
  } else {
    digitalWrite(TX_PIN, ledOn ? HIGH : LOW);
  }
}

uint32_t brightnessPercentToDuty(uint8_t percent) {
  if (percent > 100) percent = 100;

  uint32_t activeHighDuty = (uint32_t)percent * PWM_MAX_DUTY / 100;

  if (LED_ACTIVE_LOW) {
    // Active-low PWM inversion:
    // brightness 100% -> duty 0   -> GPIO mostly LOW  -> LED brightest
    // brightness 0%   -> duty 255 -> GPIO mostly HIGH -> LED dimmest/off
    return PWM_MAX_DUTY - activeHighDuty;
  }

  // Active-high MOSFET gate drive:
  // brightness 100% -> duty 255 -> GPIO mostly HIGH -> LED brightest
  // brightness 0%   -> duty 0   -> GPIO mostly LOW  -> LED dimmest/off
  return activeHighDuty;
}

void setBrightnessPercent(uint8_t percent) {
  writePwmDuty(brightnessPercentToDuty(percent));
}

void txIdle() {
  setBrightnessPercent(LED_IDLE_BRIGHTNESS_PERCENT);
}

void txBright() {
  setBrightnessPercent(LED_BRIGHT_PERCENT);
}

void txDim() {
  setBrightnessPercent(LED_DIM_PERCENT);
}

void txBoundaryCarrier() {
  // Continuous boundary carrier: frame boundaries should sit at the same
  // average optical brightness as the Manchester stream, not at full bright
  // or full dim. This avoids visible brightness jumps without changing the
  // optical frame format or the RX decoder.
  txIdle();
}

void setup() {
#if defined(ARDUINO_ARCH_ESP32)
  Serial.setRxBufferSize(8192);
#endif

  Serial.begin(115200);
  Serial.setTimeout(25);

  setupPwmOutput();
  txIdle();

  setFrequency(frequencyHz);

  Serial.println("ESP32 TX Ready - DC-biased PWM Manchester idle bright");
  Serial.print("PWM carrier = ");
  Serial.print(PWM_FREQ_HZ);
  Serial.print(" Hz | bright = ");
  Serial.print(LED_BRIGHT_PERCENT);
  Serial.print("% | dim = ");
  Serial.print(LED_DIM_PERCENT);
  Serial.println("%");
  Serial.print("LED polarity = ");
  Serial.println(LED_ACTIVE_LOW ? "active-low" : "active-high");
}

void loop() {
  if (!Serial.available()) return;

  int peeked = Serial.peek();

  if (peeked >= 'A' && peeked <= 'Z') {
    handleCommand();
    return;
  }

  if (peeked != START_BYTE) {
    Serial.read();
    return;
  }

  Serial.read();

  int typeRead = readByteWithTimeout(1000);
  if (typeRead < 0) {
    Serial.println("TX_ERROR: timeout reading frame type");
    txIdle();
    return;
  }

  uint8_t frameType = (uint8_t)typeRead;

  int msb = readByteWithTimeout(1000);
  int lsb = readByteWithTimeout(1000);

  if (msb < 0 || lsb < 0) {
    Serial.println("TX_ERROR: timeout reading size");
    txIdle();
    return;
  }

  uint16_t size = ((uint16_t)msb << 8) | (uint16_t)lsb;

  int crcMsb = readByteWithTimeout(1000);
  int crcLsb = readByteWithTimeout(1000);

  if (crcMsb < 0 || crcLsb < 0) {
    Serial.println("TX_ERROR: timeout reading CRC");
    txIdle();
    return;
  }

  uint16_t frameCRC = ((uint16_t)crcMsb << 8) | (uint16_t)crcLsb;

  if (frameType != TYPE_CAROUSEL_CHUNK && frameType != TYPE_CAROUSEL_PARITY) {
    Serial.print("TX_ERROR: unknown frame type 0x");
    Serial.println(frameType, HEX);
    discardBytes(size);
    txIdle();
    return;
  }

  uint8_t *payload = nullptr;

  if (size > 0) {
    payload = (uint8_t *)malloc(size);

    if (!payload) {
      Serial.println("TX_ERROR: cannot allocate payload buffer");
      discardBytes(size);
      txIdle();
      return;
    }

    if (!readExact(payload, size, 15000)) {
      Serial.println("TX_ERROR: timeout reading payload from GUI");
      free(payload);
      txIdle();
      return;
    }
  }

  sendFrameGap();
  uint32_t txDeadline = micros();

  sendManchesterPreamble(PREAMBLE_COUNT, txDeadline);

  sendManchesterByte(START_BYTE, txDeadline);
  sendManchesterByte(frameType, txDeadline);
  sendManchesterByte((size >> 8) & 0xFF, txDeadline);
  sendManchesterByte(size & 0xFF, txDeadline);
  sendManchesterByte((frameCRC >> 8) & 0xFF, txDeadline);
  sendManchesterByte(frameCRC & 0xFF, txDeadline);

  for (uint16_t i = 0; i < size; i++) {
    sendManchesterByte(payload[i], txDeadline);
  }

  txBoundaryCarrier();

  if (payload) free(payload);

  framesSentSinceBoot++;

  if (quietMode) {
    if (framesSentSinceBoot % QUIET_PROGRESS_EVERY_FRAMES == 0) {
      Serial.print("TX_BULK_PROGRESS: ");
      Serial.print(framesSentSinceBoot);
      Serial.println(" frames");
    }
  } else {
    Serial.print("TX_CAROUSEL_FRAME_SENT: ");
    Serial.print(size);
    Serial.println(" bytes payload");
  }
}

int readByteWithTimeout(uint32_t timeoutMs) {
  uint32_t start = millis();

  while (!Serial.available()) {
    if (millis() - start > timeoutMs) return -1;
    delay(1);
  }

  return Serial.read();
}

bool readExact(uint8_t *buffer, uint16_t len, uint32_t timeoutMs) {
  uint16_t received = 0;
  uint32_t lastByteTime = millis();

  while (received < len) {
    while (Serial.available() && received < len) {
      buffer[received++] = (uint8_t)Serial.read();
      lastByteTime = millis();
    }

    if (millis() - lastByteTime > timeoutMs) return false;

    delay(1);
  }

  return true;
}

void discardBytes(uint16_t n) {
  uint32_t start = millis();
  uint16_t discarded = 0;

  while (discarded < n && millis() - start < 2000) {
    if (Serial.available()) {
      Serial.read();
      discarded++;
    } else {
      delay(1);
    }
  }
}

void handleCommand() {
  String line = Serial.readStringUntil('\n');
  line.trim();

  if (line.startsWith("FREQ=")) {
    uint32_t newFreq = line.substring(5).toInt();
    setFrequency(newFreq);
    return;
  }

  if (line.startsWith("QUIET=")) {
    quietMode = (line.substring(6).toInt() != 0);
    Serial.print("TX quiet mode ");
    Serial.println(quietMode ? "enabled" : "disabled");
    return;
  }

  if (line.startsWith("LEDTEST")) {
    runLedTest();
    return;
  }

  Serial.print("TX: unknown command ");
  Serial.println(line);
}

void runLedTest() {
  Serial.println("TX_LED_TEST_START");

  // Make this a true human-visible control test, not a PWM brightness test.
  // PWM at 40 kHz reads as an average voltage on a multimeter and may not look
  // like an obvious blink. Detach PWM briefly and drive the gate fully ON/OFF.
  detachPwmOutput();
  pinMode(TX_PIN, OUTPUT);

  for (uint8_t i = 0; i < 5; i++) {
    writeLedDigital(false);
    delay(450);
    writeLedDigital(true);
    delay(450);
  }

  writeLedDigital(false);
  delay(250);
  setupPwmOutput();
  txIdle();
  Serial.println("TX_LED_TEST_DONE");
}

void sendFrameGap() {
  txBoundaryCarrier();

  if (FRAME_GAP_US > 0) {
    delayMicroseconds(FRAME_GAP_US);
  }
}

void sendManchesterPreamble(uint8_t count, uint32_t &deadline) {
  for (uint8_t i = 0; i < count; i++) {
    sendManchesterByte(PREAMBLE_BYTE, deadline);
  }
}

void setFrequency(uint32_t f) {
  if (f < 1) {
    Serial.println("TX: FREQ too low, using 1 Hz");
    f = 1;
  } else if (f > MAX_FREQUENCY_HZ) {
    Serial.print("TX: FREQ too high, using ");
    Serial.print(MAX_FREQUENCY_HZ);
    Serial.println(" Hz");
    f = MAX_FREQUENCY_HZ;
  }

  frequencyHz = f;
  halfBitUs = 1000000UL / (2 * frequencyHz);

  if (halfBitUs < 1) halfBitUs = 1;

  Serial.print("TX FREQ = ");
  Serial.print(frequencyHz);
  Serial.print(" Hz | halfBit = ");
  Serial.print(halfBitUs);
  Serial.println(" us");
}

void waitUntilMicros(uint32_t deadline) {
  while ((int32_t)(micros() - deadline) < 0) {
    ;
  }
}

void waitNextHalfBit(uint32_t &deadline) {
  deadline += halfBitUs;
  waitUntilMicros(deadline);
}

void sendManchesterByte(uint8_t b, uint32_t &deadline) {
  // Start symbol: still Manchester-shaped, but uses bright/dim levels.
  txDim();
  waitNextHalfBit(deadline);
  txBright();
  waitNextHalfBit(deadline);

  for (int i = 7; i >= 0; i--) {
    bool bit = (b >> i) & 0x01;

    if (bit) {
      txBright();
      waitNextHalfBit(deadline);
      txDim();
      waitNextHalfBit(deadline);
    } else {
      txDim();
      waitNextHalfBit(deadline);
      txBright();
      waitNextHalfBit(deadline);
    }
  }

  txBoundaryCarrier();
  waitNextHalfBit(deadline);
}
