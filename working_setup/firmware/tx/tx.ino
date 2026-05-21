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
const uint32_t OOK_FRAME_GAP_MIN_US = 2000;
const uint32_t OOK_FRAME_GAP_MAX_US = 12000;
const uint32_t PWM_FRAME_GAP_US = 0;
const uint16_t QUIET_PROGRESS_EVERY_FRAMES = 32;

// Transmission modes:
//   OOK: direct ON/OFF Manchester. This is the stable default for the current
//        BPW34 + OPA2604 + LM393 receiver because it gives maximum optical contrast.
//   PWM: experimental DC-biased Manchester. The LED never fully turns off;
//        symbols switch between bright and dim PWM levels to reduce visible
//        brightness pumping, but it may be harder for a simple RX to decode.
enum TxOpticalMode : uint8_t {
  TX_MODE_OOK = 0,
  TX_MODE_PWM = 1,
};

// DC-biased PWM settings used only when TX_MODE_PWM is selected.
// 40 kHz PWM is far above the 9 kHz LiFi data frequency. Human eyes mostly
// see the average brightness, while the RX sees the Manchester bright/dim
// envelope. If the RX struggles, use the default ON/OFF mode.
const uint32_t PWM_FREQ_HZ = 40000;
const uint8_t PWM_RESOLUTION_BITS = 8;
const uint8_t PWM_CHANNEL = 0;
const uint32_t PWM_MAX_DUTY = (1UL << PWM_RESOLUTION_BITS) - 1;

// Current preserved TX hardware is the 2N3904 + IRF540N LED driver path.
// Verify the real LED polarity with LEDTEST before changing LED_ACTIVE_LOW.
// Active-high behavior:
// GPIO HIGH -> MOSFET ON -> LED brighter.
// If your actual wiring still behaves as active-low, change this to true.
const bool LED_ACTIVE_LOW = false;

// PWM recovery defaults. Start with a large bright/dim difference because the
// current RX is a BPW34 + OPA2604 + LM393 receiver and needs strong contrast. Once OOK
// is stable again, you can reduce the gap gradually, for example 100/60/80,
// 100/70/85, then 96/76/86.
//
// Idle is set near the average of bright/dim states: (100 + 50) / 2 = 75.
// Matching idle brightness to the average transmission brightness reduces
// low-frequency envelope flicker at chunk/frame boundaries, round gaps, and
// txIdle() transitions.
const uint8_t LED_IDLE_BRIGHTNESS_PERCENT = 75;
const uint8_t LED_BRIGHT_PERCENT = 100;
const uint8_t LED_DIM_PERCENT = 50;

uint32_t frequencyHz = 1000;
uint32_t halfBitUs = 500;
bool quietMode = false;
TxOpticalMode txMode = TX_MODE_OOK;
uint32_t framesSentSinceBoot = 0;
bool pwmAttached = false;

void setupPwmOutput() {
  if (pwmAttached) return;

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(TX_PIN, PWM_FREQ_HZ, PWM_RESOLUTION_BITS);
#else
  ledcSetup(PWM_CHANNEL, PWM_FREQ_HZ, PWM_RESOLUTION_BITS);
  ledcAttachPin(TX_PIN, PWM_CHANNEL);
#endif

  pwmAttached = true;
}

void writePwmDuty(uint32_t duty) {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(TX_PIN, duty);
#else
  ledcWrite(PWM_CHANNEL, duty);
#endif
}

void detachPwmOutput() {
  if (!pwmAttached) return;

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcDetach(TX_PIN);
#else
  ledcDetachPin(TX_PIN);
#endif

  pwmAttached = false;
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
  setupPwmOutput();
  writePwmDuty(brightnessPercentToDuty(percent));
}

void txIdle() {
  if (txMode == TX_MODE_PWM) {
    setBrightnessPercent(LED_IDLE_BRIGHTNESS_PERCENT);
  } else {
    writeLedDigital(true);
  }
}

void txBright() {
  if (txMode == TX_MODE_PWM) {
    setBrightnessPercent(LED_BRIGHT_PERCENT);
  } else {
    writeLedDigital(true);
  }
}

void txDim() {
  if (txMode == TX_MODE_PWM) {
    setBrightnessPercent(LED_DIM_PERCENT);
  } else {
    writeLedDigital(false);
  }
}

void txBoundaryCarrier() {
  // In PWM mode, frame boundaries sit near the average optical brightness to
  // reduce visible envelope flicker. In OOK mode, keep the historical idle-ON
  // behavior that the existing receiver timing was tuned around.
  txIdle();
}

const char *txModeName() {
  return txMode == TX_MODE_PWM ? "DC_PWM" : "ON_OFF";
}

void printTxDiagnostics() {
  Serial.print("TX_MODE:");
  Serial.println(txModeName());
  Serial.print("TX_LED_PIN:");
  Serial.println(TX_PIN);
  Serial.print("TX_LED_ACTIVE_LOW:");
  Serial.println(LED_ACTIVE_LOW ? 1 : 0);
  Serial.print("TX_POLARITY:");
  Serial.println(LED_ACTIVE_LOW ? "ACTIVE_LOW_2N3904_DRIVER" : "ACTIVE_HIGH_2N3904_IRF540N_DRIVER");
  Serial.print("TX_PWM:freq=");
  Serial.print(PWM_FREQ_HZ);
  Serial.print(":resolution=");
  Serial.print(PWM_RESOLUTION_BITS);
  Serial.print(":maxDuty=");
  Serial.println(PWM_MAX_DUTY);
  Serial.print("TX_BRIGHTNESS:bright=");
  Serial.print(LED_BRIGHT_PERCENT);
  Serial.print(":dim=");
  Serial.print(LED_DIM_PERCENT);
  Serial.print(":idle=");
  Serial.println(LED_IDLE_BRIGHTNESS_PERCENT);
  Serial.print("TX_FREQ:");
  Serial.print(frequencyHz);
  Serial.print(":halfBitUs=");
  Serial.println(halfBitUs);
}

void setTxMode(TxOpticalMode mode) {
  txMode = mode;

  if (txMode == TX_MODE_PWM) {
    setupPwmOutput();
  } else {
    detachPwmOutput();
    pinMode(TX_PIN, OUTPUT);
  }

  txIdle();

  Serial.print("TXMODE_SET:");
  Serial.println(txModeName());
  printTxDiagnostics();
}

void setup() {
#if defined(ARDUINO_ARCH_ESP32)
  Serial.setRxBufferSize(8192);
#endif

  Serial.begin(115200);
  Serial.setTimeout(25);

  pinMode(TX_PIN, OUTPUT);
  setTxMode(TX_MODE_OOK);

  setFrequency(frequencyHz);

  Serial.println("ESP32 TX Ready - dual-mode Manchester LiFi");
  Serial.println("Default optical mode = ON_OFF stable");
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

  if (line.startsWith("TXMODE=") || line.startsWith("MODE=")) {
    int equals = line.indexOf('=');
    String mode = line.substring(equals + 1);
    mode.trim();
    mode.toUpperCase();

    if (mode == "PWM" || mode == "DC_PWM" || mode == "DC") {
      setTxMode(TX_MODE_PWM);
    } else if (mode == "OOK" || mode == "ON_OFF" || mode == "ONOFF") {
      setTxMode(TX_MODE_OOK);
    } else {
      Serial.print("TX_ERROR: unknown optical mode ");
      Serial.println(mode);
    }
    return;
  }

  if (line.startsWith("LEDTEST")) {
    runLedTest();
    return;
  }

  if (line.startsWith("STATS")) {
    printTxDiagnostics();
    return;
  }

  Serial.print("TX: unknown command ");
  Serial.println(line);
}

void runLedTest() {
  Serial.println("TX_LED_TEST_START");

  // Human-visible control test. It temporarily forces direct GPIO drive even
  // when PWM mode is selected, so a multimeter and the LED should show clear
  // full-scale ON/OFF changes through the 2N3904 + IRF540N driver.
  TxOpticalMode previousMode = txMode;
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
  setTxMode(previousMode);
  Serial.println("TX_LED_TEST_DONE");
}

void sendFrameGap() {
  txBoundaryCarrier();

  if (txMode == TX_MODE_PWM) {
    if (PWM_FRAME_GAP_US > 0) {
      delayMicroseconds(PWM_FRAME_GAP_US);
    }
    return;
  }

  // ON/OFF mode needs a small quiet interval so the simple RX can reliably
  // re-lock onto the next preamble. Keep it bounded to avoid long visible
  // packet-envelope pauses.
  uint32_t gap = halfBitUs * 80UL;
  if (gap < OOK_FRAME_GAP_MIN_US) gap = OOK_FRAME_GAP_MIN_US;
  if (gap > OOK_FRAME_GAP_MAX_US) gap = OOK_FRAME_GAP_MAX_US;
  if (gap > 0) {
    delayMicroseconds(gap);
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
