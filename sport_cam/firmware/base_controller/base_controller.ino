/**
 * SportCam base controller — ESP32 DevKitC
 *
 * Pan stepper (TMC2209, StealthChop), WS2812B status ring, hall-sensor
 * homing, WebSocket client to the home server.
 *
 * Libraries (Library Manager):
 *   FastAccelStepper, FastLED, ArduinoWebsockets (gilmaimon), ArduinoJson
 *
 * Board: "ESP32 Dev Module"
 */
#include <WiFi.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>
#include <FastAccelStepper.h>
#include <FastLED.h>

// ---- configuration ---------------------------------------------------------
const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASS = "YOUR_PASS";
const char* SERVER_WS = "ws://homeserver.local:8787/ws/device";

const int PIN_STEP = 25;
const int PIN_DIR  = 26;
const int PIN_NEN  = 27;
const int PIN_LED  = 18;
const int PIN_HALL = 34;

const int   NUM_LEDS       = 16;
const float GEAR_RATIO     = 3.0f;              // 60T / 20T belt
const float STEPS_PER_DEG  = 200.0f * 16 * GEAR_RATIO / 360.0f;  // 26.67
const float MAX_DPS        = 200.0f;            // absolute slew ceiling
const uint32_t CMD_TIMEOUT_MS = 500;            // no panVel → stop

// ---- state -----------------------------------------------------------------
using namespace websockets;
WebsocketsClient ws;
FastAccelStepperEngine engine;
FastAccelStepper* stepper = nullptr;
CRGB leds[NUM_LEDS];

String   camState     = "idle";
uint32_t lastCmdMs    = 0;
uint32_t lastReportMs = 0;

// ---- LED -------------------------------------------------------------------
void renderLeds() {
  CRGB c = CRGB::Black;
  uint8_t v = 255;
  if (camState == "idle")      c = CRGB(0x2F, 0x6F, 0xED);   // solid blue
  else if (camState == "tracking")  c = CRGB(0x1F, 0x9D, 0x55);  // solid green
  else if (camState == "recording") {                        // breathing red
    v = beatsin8(30, 40, 255);
    c = CRGB(0xD6, 0x45, 0x41);
  }
  fill_solid(leds, NUM_LEDS, c);
  FastLED.setBrightness(v);
  FastLED.show();
}

// ---- messaging -------------------------------------------------------------
void onMessage(WebsocketsMessage msg) {
  JsonDocument doc;
  if (deserializeJson(doc, msg.data())) return;
  const char* type = doc["type"];
  if (!type) return;

  if (strcmp(type, "state") == 0) {
    camState = String((const char*)doc["state"]);
    if (camState == "idle" || camState == "off") stepper->stopMove();
  } else if (strcmp(type, "panVel") == 0) {
    float dps = constrain((float)doc["dps"], -MAX_DPS, MAX_DPS);
    lastCmdMs = millis();
    int32_t hz = (int32_t)(fabsf(dps) * STEPS_PER_DEG);
    if (hz < 5) {
      stepper->stopMove();
    } else {
      stepper->setSpeedInHz(hz);
      if (dps >= 0) stepper->runForward();
      else          stepper->runBackward();
    }
  }
}

void connectWs() {
  ws.onMessage(onMessage);
  while (!ws.connect(SERVER_WS)) delay(1000);
  ws.send("{\"type\":\"hello\",\"device\":\"base\",\"caps\":[\"pan\",\"led\"]}");
}

// ---- setup / loop ----------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_HALL, INPUT);

  FastLED.addLeds<WS2812B, PIN_LED, GRB>(leds, NUM_LEDS);

  engine.init();
  stepper = engine.stepperConnectToPin(PIN_STEP);
  stepper->setDirectionPin(PIN_DIR);
  stepper->setEnablePin(PIN_NEN, /*low_active=*/true);
  stepper->setAutoEnable(true);
  stepper->setAcceleration((uint32_t)(360.0f * STEPS_PER_DEG));  // 360°/s²

  // TMC2209 defaults via UART could be set here (microsteps, current);
  // most stepstick carriers ship at 16 µsteps via MS pins which matches
  // STEPS_PER_DEG above.

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) delay(300);
  connectWs();

  // Home: rotate slowly until the hall sensor sees the platform magnet.
  stepper->setSpeedInHz((uint32_t)(20 * STEPS_PER_DEG));
  stepper->runForward();
  uint32_t t0 = millis();
  while (digitalRead(PIN_HALL) == HIGH && millis() - t0 < 25000) delay(2);
  stepper->forceStopAndNewPosition(0);
}

void loop() {
  if (!ws.available()) connectWs();
  ws.poll();

  // Dead-man: stop panning if commands stop arriving.
  if (millis() - lastCmdMs > CMD_TIMEOUT_MS && stepper->isRunning()) {
    stepper->stopMove();
  }

  // Re-zero the dead-reckoned angle whenever the magnet passes.
  if (digitalRead(PIN_HALL) == LOW) {
    int32_t whole = (int32_t)(360.0f * STEPS_PER_DEG);
    stepper->setCurrentPosition(stepper->getCurrentPosition() % whole);
  }

  // Report absolute pan angle at 5 Hz.
  if (millis() - lastReportMs > 200) {
    lastReportMs = millis();
    float deg = fmodf(stepper->getCurrentPosition() / STEPS_PER_DEG, 360.0f);
    if (deg < 0) deg += 360.0f;
    char buf[64];
    snprintf(buf, sizeof(buf), "{\"type\":\"telemetry\",\"pan\":%.1f}", deg);
    ws.send(buf);
  }

  renderLeds();
  delay(5);
}
