/**
 * SportCam wearable tag — ESP32 + DW1000 (Makerfabs ESP32-UWB or compatible)
 *
 * DS-TWR responder: answers ranging polls from the two head anchors at up to
 * 20 Hz. Button: short press = re-acquire, long press (>1 s) = toggle
 * recording. Button events go out as a brief BLE advertisement
 * ("SPORTCAM-BTN:<kind>"); the Pi head service scans for it and relays
 * {"type":"tagButton","kind":"long"} to the server (stock DW1000Ranging has
 * no user-payload API, and BLE costs nothing extra on an ESP32).
 *
 * Libraries: arduino-dw1000 (Makerfabs fork: mf-DW1000), ESP32 BLE (bundled)
 * Board: "ESP32 Dev Module"
 */
#include <SPI.h>
#include <DW1000.h>
#include <DW1000Ranging.h>
#include <BLEDevice.h>
#include <BLEAdvertising.h>

// Makerfabs ESP32-UWB pin map
const uint8_t PIN_RST = 27;
const uint8_t PIN_IRQ = 34;
const uint8_t PIN_SS  = 4;

const int PIN_BTN = 13;   // to GND, INPUT_PULLUP
const int PIN_LED = 2;
const int PIN_VBAT = 35;  // divider on battery (board-dependent)

const char TAG_ADDR[] = "7D:00:22:EA:82:60:3B:9C";

uint32_t btnDownMs = 0;
uint32_t lastRangeMs = 0;
uint32_t advStopMs = 0;
BLEAdvertising* adv = nullptr;

void newRange() {
  lastRangeMs = millis();
  digitalWrite(PIN_LED, !digitalRead(PIN_LED));  // blink on activity
}

void advertiseButton(const char* kind) {
  // 500 ms burst of advertisements carrying the event in the device name.
  BLEAdvertisementData data;
  data.setName(String("SPORTCAM-BTN:") + kind);
  adv->setAdvertisementData(data);
  adv->start();
  advStopMs = millis() + 500;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);

  BLEDevice::init("SPORTCAM-TAG");
  adv = BLEDevice::getAdvertising();

  SPI.begin(18, 19, 23);
  DW1000Ranging.initCommunication(PIN_RST, PIN_SS, PIN_IRQ);
  DW1000Ranging.attachNewRange(newRange);
  DW1000Ranging.startAsTag(const_cast<char*>(TAG_ADDR),
                           DW1000.MODE_LONGDATA_RANGE_LOWPOWER);
}

void loop() {
  DW1000Ranging.loop();

  // Button handling
  if (digitalRead(PIN_BTN) == LOW) {
    if (btnDownMs == 0) btnDownMs = millis();
  } else if (btnDownMs != 0) {
    uint32_t held = millis() - btnDownMs;
    btnDownMs = 0;
    if (held > 1000) advertiseButton("long");    // toggle recording
    else             advertiseButton("short");   // re-acquire
  }
  if (advStopMs && millis() > advStopMs) {
    adv->stop();
    advStopMs = 0;
  }

  // Deep sleep after 10 min with no anchor contact (battery protection).
  if (millis() - lastRangeMs > 600000UL && lastRangeMs != 0) {
    esp_sleep_enable_ext0_wakeup((gpio_num_t)PIN_BTN, 0);
    esp_deep_sleep_start();
  }
}
