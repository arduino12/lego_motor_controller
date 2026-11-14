// remote_catcher: plays the "powerbox" car as a BLE *central*, with the car's own public address.
// Hypothesis: the car's remote is a BLE peripheral that (after pairing) sends directed advertising
// to the car's address, so only a scanner with that address ever hears it, and the car connects to it.
// This firmware prints every advertisement (directed ones always, others above MIN_RSSI), auto-connects
// to the first device that sends us directed advertising, dumps its whole GATT table, subscribes to
// everything that notifies/indicates, and prints every value it sends.
// Serial: 'a' toggle auto-connect, 'r' restart scanning, 'd' disconnect.
#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEClient.h>
#include <BLEScan.h>
#include <esp_mac.h>
#include <esp_gap_ble_api.h>

static const uint8_t CAR_MAC[6] = {0x25, 0x02, 0x00, 0x00, 0x1c, 0x43};
static const int MIN_RSSI = -60;
static const char *EVT[] = {"ADV_IND", "DIRECT_IND", "SCAN_IND", "NONCONN_IND", "SCAN_RSP"};

struct Seen { uint8_t bda[6]; uint8_t evt; uint32_t lastPrint; uint8_t len; uint8_t data[62]; };
static Seen seen[48];
static int nSeen;

static volatile bool want, connected, autoConnect = true;
static uint8_t wantBda[6], wantType;
static BLEClient *client;

static String hexs(const uint8_t *d, size_t n) {
  String s; char b[4];
  for (size_t i = 0; i < n; i++) { snprintf(b, sizeof b, "%s%02x", i ? " " : "", d[i]); s += b; }
  return s;
}
static String mac(const uint8_t *a) {
  char b[18]; snprintf(b, sizeof b, "%02x:%02x:%02x:%02x:%02x:%02x", a[0], a[1], a[2], a[3], a[4], a[5]);
  return b;
}

// Raw GAP events, before the BLE library sees them: the only place directed advertising shows up.
static void gapHandler(esp_gap_ble_cb_event_t ev, esp_ble_gap_cb_param_t *p) {
  if (ev != ESP_GAP_BLE_SCAN_RESULT_EVT || p->scan_rst.search_evt != ESP_GAP_SEARCH_INQ_RES_EVT) return;
  auto &r = p->scan_rst;
  bool directed = r.ble_evt_type == ESP_BLE_EVT_CONN_DIR_ADV;
  if (!directed && r.rssi < MIN_RSSI) return;
  uint8_t len = r.adv_data_len + r.scan_rsp_len;
  Seen *s = nullptr;
  for (int i = 0; i < nSeen; i++)
    if (!memcmp(seen[i].bda, r.bda, 6) && seen[i].evt == r.ble_evt_type) { s = &seen[i]; break; }
  bool changed = !s || s->len != len || memcmp(s->data, r.ble_adv, len);
  if (!s && nSeen < 48) { s = &seen[nSeen++]; memcpy(s->bda, r.bda, 6); s->evt = r.ble_evt_type; s->lastPrint = 0; }
  if (s && !changed && millis() - s->lastPrint < 5000) return;
  if (s) { s->len = len; memcpy(s->data, r.ble_adv, len); s->lastPrint = millis(); }
  Serial.printf("%10lu %-11s %s atype=%u rssi=%d data=[%s]\n", millis(), EVT[r.ble_evt_type < 5 ? r.ble_evt_type : 0],
                mac(r.bda).c_str(), r.ble_addr_type, r.rssi, hexs(r.ble_adv, len).c_str());
  if (directed && autoConnect && !want && !connected) {
    memcpy(wantBda, r.bda, 6); wantType = r.ble_addr_type; want = true;
  }
}

class ClientCB : public BLEClientCallbacks {
  void onConnect(BLEClient *c) override { connected = true; Serial.printf("%10lu CONNECTED\n", millis()); }
  void onDisconnect(BLEClient *c) override { connected = false; Serial.printf("%10lu DISCONNECTED\n", millis()); }
};

static void onNotify(BLERemoteCharacteristic *c, uint8_t *d, size_t n, bool isNotify) {
  Serial.printf("%10lu %s h=%04x %s len=%u: %s\n", millis(), isNotify ? "NOTIFY" : "INDICATE", c->getHandle(),
                c->getUUID().toString().c_str(), (unsigned)n, hexs(d, n).c_str());
}

static void startScan() {
  BLEScan *scan = BLEDevice::getScan();
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);
  scan->clearResults();
  scan->start(0, nullptr, false);
  Serial.printf("%10lu scanning as %s (auto-connect %s)\n", millis(), BLEDevice::getAddress().toString().c_str(),
                autoConnect ? "on" : "off");
}

static void connectAndDump() {
  BLEDevice::getScan()->stop();
  delay(200);
  Serial.printf("%10lu connecting to %s type %u ...\n", millis(), mac(wantBda).c_str(), wantType);
  if (!client) { client = BLEDevice::createClient(); client->setClientCallbacks(new ClientCB()); }
  if (!client->connect(BLEAddress(wantBda), wantType, 6000)) {
    Serial.printf("%10lu connect FAILED\n", millis());
    startScan();
    return;
  }
  auto *svcs = client->getServices();
  Serial.printf("%10lu GATT: %u services\n", millis(), (unsigned)svcs->size());
  for (auto &sv : *svcs) {
    BLERemoteService *s = sv.second;
    Serial.printf("  service %s (h=%04x)\n", s->getUUID().toString().c_str(), s->getHandle());
    for (auto &ch : *s->getCharacteristics()) {
      BLERemoteCharacteristic *c = ch.second;
      Serial.printf("    char %s h=%04x [%s%s%s%s]\n", c->getUUID().toString().c_str(), c->getHandle(),
                    c->canRead() ? "read " : "", c->canWrite() ? "write " : "", c->canNotify() ? "notify " : "",
                    c->canIndicate() ? "indicate" : "");
      if (c->canRead()) {
        String v = c->readValue();
        Serial.printf("      value: [%s]\n", hexs((const uint8_t *)v.c_str(), v.length()).c_str());
      }
      if (c->canNotify() || c->canIndicate()) {
        c->registerForNotify(onNotify, c->canNotify());
        Serial.println("      subscribed");
      }
    }
  }
  Serial.printf("%10lu ready: press the remote's buttons\n", millis());
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.printf("\nset BT MAC: %s\n", esp_err_to_name(esp_iface_mac_addr_set(CAR_MAC, ESP_MAC_BT)));
  BLEDevice::init("powerbox");
  BLEDevice::setCustomGapHandler(gapHandler);
  startScan();
}

void loop() {
  static uint32_t t;
  if (want) { want = false; connectAndDump(); }
  if (millis() - t > 15000) {
    t = millis();
    Serial.printf("%10lu alive%s\n", millis(), connected ? " (connected)" : "");
    if (!connected) BLEDevice::getScan()->clearResults();
  }
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'a') { autoConnect = !autoConnect; Serial.printf("auto-connect %s\n", autoConnect ? "on" : "off"); }
    if (c == 'r') { BLEDevice::getScan()->stop(); startScan(); }
    if (c == 'd' && client && connected) client->disconnect();
  }
  delay(20);
}
