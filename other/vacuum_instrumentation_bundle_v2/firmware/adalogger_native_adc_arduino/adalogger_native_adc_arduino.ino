/*
  Adafruit Feather RP2040 Adalogger - native ADC 0-10 V DAQ example

  Four analog channels use the RP2040's onboard 12-bit ADCs (A0-A3).
  Each input MUST be scaled before it reaches the Feather. The reference
  front end is:

      instrument -- 30.1k --+-- AIN (A0..A3)
                             |
                           10.0k
                             |
                            GND

      100 nF from AIN to GND

  Divider gain (instrument volts / ADC volts) = 4.01.
  Thus 10 V -> ~2.494 V at the RP2040 ADC and 13.23 V -> ~3.3 V.

  USB serial protocol is intentionally compatible with the ADS1115 example:
      PING
      INFO
      READ
      START
      STOP
      RATE <Hz>   (0.2 to 50 Hz)

  Streamed samples are newline-delimited JSON:
      {"type":"sample","t_us":123456,"volts":[4.0001,5.0002,0.0,0.0]}

  IMPORTANT:
  - ADC_REFERENCE_V is nominal. For better absolute accuracy, measure the
    board's 3.3 V rail/reference behavior and calibrate each channel against
    a trustworthy DMM using CAL_SCALE and CAL_OFFSET_V.
  - Averaging reduces random noise but does not remove RP2040 ADC INL/DNL.
  - This is a non-isolated DAQ. Check ground potentials before connecting
    multiple line-powered instruments.
*/

#include <Arduino.h>

static const uint8_t ADC_PINS[4] = {A0, A1, A2, A3};

// Reference/front-end constants.
static constexpr float ADC_REFERENCE_V = 3.3000f;
static constexpr float ADC_MAX_CODE = 4095.0f;
static constexpr float R_TOP_OHM = 30100.0f;
static constexpr float R_BOTTOM_OHM = 10000.0f;
static constexpr float DIVIDER_GAIN = (R_TOP_OHM + R_BOTTOM_OHM) / R_BOTTOM_OHM; // 4.01

// Channel calibration. After comparing against a DMM, use:
// V_corrected = V_uncalibrated * CAL_SCALE[ch] + CAL_OFFSET_V[ch]
static float CAL_SCALE[4] = {1.0f, 1.0f, 1.0f, 1.0f};
static float CAL_OFFSET_V[4] = {0.0f, 0.0f, 0.0f, 0.0f};

static uint16_t averagesPerReading = 64;
static bool streaming = false;
static float sampleRateHz = 10.0f;
static uint32_t nextSampleUs = 0;

String lineBuffer;

float readInstrumentVoltage(uint8_t channel) {
  uint32_t sum = 0;
  for (uint16_t i = 0; i < averagesPerReading; ++i) {
    sum += analogRead(ADC_PINS[channel]);
  }

  const float avgCode = static_cast<float>(sum) / averagesPerReading;
  const float adcVolts = (avgCode / ADC_MAX_CODE) * ADC_REFERENCE_V;
  const float inputVolts = adcVolts * DIVIDER_GAIN;
  return inputVolts * CAL_SCALE[channel] + CAL_OFFSET_V[channel];
}

void emitSample() {
  const uint32_t t = micros();
  float v[4];
  for (uint8_t ch = 0; ch < 4; ++ch) {
    v[ch] = readInstrumentVoltage(ch);
  }

  Serial.print(F("{\"type\":\"sample\",\"t_us\":"));
  Serial.print(t);
  Serial.print(F(",\"volts\":["));
  for (uint8_t ch = 0; ch < 4; ++ch) {
    if (ch) Serial.print(',');
    Serial.print(v[ch], 6);
  }
  Serial.println(F("]}"));
}

void emitInfo() {
  Serial.print(F("{\"type\":\"info\",\"device\":\"adalogger_native_adc\",\"adc\":\"rp2040_12bit\",\"channels\":4,"));
  Serial.print(F("\"divider_gain\":"));
  Serial.print(DIVIDER_GAIN, 6);
  Serial.print(F(",\"adc_reference_v\":"));
  Serial.print(ADC_REFERENCE_V, 4);
  Serial.print(F(",\"averages\":"));
  Serial.print(averagesPerReading);
  Serial.println(F("}"));
}

void handleCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "PING") {
    Serial.println(F("{\"type\":\"ack\",\"command\":\"PING\",\"value\":\"PONG\"}"));
  } else if (cmd == "INFO") {
    emitInfo();
  } else if (cmd == "READ") {
    emitSample();
  } else if (cmd == "START") {
    streaming = true;
    nextSampleUs = micros();
    Serial.println(F("{\"type\":\"ack\",\"command\":\"START\"}"));
  } else if (cmd == "STOP") {
    streaming = false;
    Serial.println(F("{\"type\":\"ack\",\"command\":\"STOP\"}"));
  } else if (cmd.startsWith("RATE ")) {
    const float requested = cmd.substring(5).toFloat();
    if (requested >= 0.2f && requested <= 50.0f) {
      sampleRateHz = requested;
      Serial.print(F("{\"type\":\"ack\",\"command\":\"RATE\",\"hz\":"));
      Serial.print(sampleRateHz, 3);
      Serial.println(F("}"));
    } else {
      Serial.println(F("{\"type\":\"error\",\"message\":\"RATE must be 0.2..50 Hz\"}"));
    }
  } else {
    Serial.println(F("{\"type\":\"error\",\"message\":\"unknown command\"}"));
  }
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  for (uint8_t ch = 0; ch < 4; ++ch) pinMode(ADC_PINS[ch], INPUT);

  // USB CDC does not actually depend on this baud value. Do not block forever
  // waiting for a host so the board can start even when the laptop is absent.
  const uint32_t waitStart = millis();
  while (!Serial && (millis() - waitStart < 2500)) delay(10);
  emitInfo();
}

void loop() {
  while (Serial.available()) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n' || c == '\r') {
      if (lineBuffer.length()) {
        handleCommand(lineBuffer);
        lineBuffer = "";
      }
    } else if (lineBuffer.length() < 120) {
      lineBuffer += c;
    }
  }

  if (streaming) {
    const uint32_t now = micros();
    if (static_cast<int32_t>(now - nextSampleUs) >= 0) {
      emitSample();
      const uint32_t periodUs = static_cast<uint32_t>(1000000.0f / sampleRateHz);
      nextSampleUs += periodUs;
      // Recover gracefully after a long stall.
      if (static_cast<int32_t>(now - nextSampleUs) > static_cast<int32_t>(periodUs * 2U)) {
        nextSampleUs = now + periodUs;
      }
    }
  }
}
