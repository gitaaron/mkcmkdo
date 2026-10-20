/**
 * SportCam UWB anchor — ESP32 + DW1000 (one sketch for both anchors A1/A2)
 *
 * DS-TWR initiator. Prints one line per completed exchange over USB serial
 * (the Pi head service reads /dev/ttyUSB0 and /dev/ttyUSB1):
 *
 *     R,<tag_short_addr>,<range_m>
 *
 * Flash the same sketch to both anchors, changing ANCHOR_ADDR's first byte
 * (0x81 for A1, 0x82 for A2).
 *
 * Library: arduino-dw1000 (Makerfabs fork: mf-DW1000)
 * Board: "ESP32 Dev Module"
 */
#include <SPI.h>
#include <DW1000.h>
#include <DW1000Ranging.h>

const uint8_t PIN_RST = 27;
const uint8_t PIN_IRQ = 34;
const uint8_t PIN_SS  = 4;

// A1: "81:..." — A2: flash with "82:..."
const char ANCHOR_ADDR[] = "81:00:5B:D5:A9:9A:E2:9C";

void newRange() {
  Serial.print("R,");
  Serial.print(DW1000Ranging.getDistantDevice()->getShortAddress(), HEX);
  Serial.print(",");
  Serial.println(DW1000Ranging.getDistantDevice()->getRange(), 3);
}

void newDevice(DW1000Device* dev) {
  Serial.print("# tag joined: ");
  Serial.println(dev->getShortAddress(), HEX);
}

void inactiveDevice(DW1000Device* dev) {
  Serial.print("# tag lost: ");
  Serial.println(dev->getShortAddress(), HEX);
}

void setup() {
  Serial.begin(115200);
  SPI.begin(18, 19, 23);
  DW1000Ranging.initCommunication(PIN_RST, PIN_SS, PIN_IRQ);
  DW1000Ranging.attachNewRange(newRange);
  DW1000Ranging.attachBlinkDevice(newDevice);
  DW1000Ranging.attachInactiveDevice(inactiveDevice);
  DW1000Ranging.startAsAnchor(const_cast<char*>(ANCHOR_ADDR),
                              DW1000.MODE_LONGDATA_RANGE_LOWPOWER);
}

void loop() {
  DW1000Ranging.loop();
}
