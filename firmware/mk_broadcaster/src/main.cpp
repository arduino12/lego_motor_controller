// mk_broadcaster: advertises whatever 24-byte Mould King telegram the host sends, as legacy
// connectable advertising: flags 02 01 02 + manufacturer data (company 0xFFF0) + 24 crypted bytes,
// exactly the on-air layout of the MK apps (31 bytes). The host does the MouldKingCrypt encoding.
// Serial lines:  D <48 hex chars>  set telegram (starts advertising)   S  stop   I <ms>  interval
//                R <hex>           set the whole raw advertising data (up to 31 bytes), e.g. a captured frame
#include <Arduino.h>
#include <BLEDevice.h>
#include <esp_gap_ble_api.h>

static uint8_t adv[31] = {0x02, 0x01, 0x02, 0x1b, 0xff, 0xf0, 0xff};
static uint8_t rawAdv[31];
static bool running;
static uint16_t itvl = 0x20;  // 0x20 * 0.625 ms = 20 ms

static void start() {
  esp_ble_adv_params_t p = {};
  p.adv_int_min = itvl;
  p.adv_int_max = itvl;
  p.adv_type = ADV_TYPE_IND;
  p.own_addr_type = BLE_ADDR_TYPE_PUBLIC;
  p.channel_map = ADV_CHNL_ALL;
  p.adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY;
  esp_ble_gap_start_advertising(&p);
  running = true;
}

static int hexv(char c) { return c <= '9' ? c - '0' : (c | 0x20) - 'a' + 10; }

void setup() {
  Serial.begin(115200);
  BLEDevice::init("");
  Serial.printf("\nmk_broadcaster ready, address %s\n", BLEDevice::getAddress().toString().c_str());
}

void loop() {
  static String line;
  while (Serial.available()) {
    char c = Serial.read();
    if (c != '\n' && c != '\r') { line += c; continue; }
    line.trim();
    if (line.startsWith("D ") && line.length() >= 2 + 48) {
      for (int i = 0; i < 24; i++) adv[7 + i] = hexv(line[2 + 2 * i]) << 4 | hexv(line[3 + 2 * i]);
      esp_ble_gap_config_adv_data_raw(adv, sizeof adv);   // updates live while advertising
      if (!running) { delay(5); start(); }
      Serial.printf("ok %lu\n", millis());
    } else if (line.startsWith("R ")) {
      String h = line.substring(2); h.replace(" ", "");
      int n = min((int)h.length() / 2, 31);
      for (int i = 0; i < n; i++) rawAdv[i] = hexv(h[2 * i]) << 4 | hexv(h[2 * i + 1]);
      esp_ble_gap_config_adv_data_raw(rawAdv, n);
      if (!running) { delay(5); start(); }
      Serial.printf("raw %d %lu\n", n, millis());
    } else if (line == "S") {
      esp_ble_gap_stop_advertising(); running = false; Serial.println("stopped");
    } else if (line.startsWith("I ")) {
      itvl = constrain(line.substring(2).toInt() * 8 / 5, 0x20, 0x4000);
      if (running) { esp_ble_gap_stop_advertising(); delay(5); start(); }
      Serial.printf("interval %u units\n", itvl);
    }
    line = "";
  }
}
