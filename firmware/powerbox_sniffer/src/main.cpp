// powerbox_sniffer: pretends to be the "powerbox" mecanum car so its remote connects here,
// then prints every write the remote makes. Same name, address, flags and service/characteristics
// (in the same order) as the real car: service ffa0, read/notify ffa2, write ffa1, all on the
// non-standard -0002- base. Uses the BLE library bundled with Arduino-ESP32 core 3.x, which runs on
// Bluedroid (classic ESP32) or NimBLE (ESP32-C3/S3): both are handled below.
// Serial commands: 'x' stop advertising, 'a' advertise again.
#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <esp_mac.h>
#if defined(CONFIG_BLUEDROID_ENABLED)
#include <BLE2902.h>
#endif

// Take over the real car's public address, in case the remote is locked to it (0 = keep the chip's own).
#define SPOOF_CAR_MAC 1
static const uint8_t CAR_MAC[6] = {0x25, 0x02, 0x00, 0x00, 0x1c, 0x43};

static const char *SVC   = "0000ffa0-0002-1000-8000-00805f9b34fb";
static const char *CH_NT = "0000ffa2-0002-1000-8000-00805f9b34fb";
static const char *CH_WR = "0000ffa1-0002-1000-8000-00805f9b34fb";

static BLECharacteristic *chWr, *chNt;
static String last;
static uint32_t lastAt, repeats;

static void flushRepeats() {
  if (repeats) Serial.printf("           (x%lu repeats)\n", (unsigned long)repeats);
  repeats = 0;
}

static void printPeer(const uint8_t *msbFirst) {
  Serial.printf("%10lu CONNECT peer=%02x:%02x:%02x:%02x:%02x:%02x\n", millis(), msbFirst[0], msbFirst[1],
                msbFirst[2], msbFirst[3], msbFirst[4], msbFirst[5]);
}

class ServerCB : public BLEServerCallbacks {
#if defined(CONFIG_BLUEDROID_ENABLED)
  void onConnect(BLEServer *s, esp_ble_gatts_cb_param_t *p) override { printPeer(p->connect.remote_bda); }
#else
  void onConnect(BLEServer *s, ble_gap_conn_desc *d) override {
    const uint8_t *a = d->peer_ota_addr.val;  // little-endian in NimBLE
    uint8_t m[6] = {a[5], a[4], a[3], a[2], a[1], a[0]};
    printPeer(m);
  }
#endif
  void onDisconnect(BLEServer *s) override {
    flushRepeats();
    Serial.printf("%10lu DISCONNECT\n", millis());
    delay(100);
    BLEDevice::startAdvertising();
  }
};

class CharCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String line = c == chWr ? "W ffa1" : "W ffa2";
    size_t n = c->getLength();
    const uint8_t *d = c->getData();
    line += " len=" + String(n) + ":";
    char b[4];
    for (size_t i = 0; i < n; i++) { snprintf(b, sizeof b, " %02x", d[i]); line += b; }
    if (line == last && millis() - lastAt < 1000) { repeats++; lastAt = millis(); return; }  // fold keep-alives
    flushRepeats();
    Serial.printf("%10lu %s\n", millis(), line.c_str());
    last = line; lastAt = millis();
  }
  void onRead(BLECharacteristic *c) override {
    Serial.printf("%10lu READ %s\n", millis(), c->getUUID().toString().c_str());
  }
#if !defined(CONFIG_BLUEDROID_ENABLED)
  void onSubscribe(BLECharacteristic *c, ble_gap_conn_desc *d, uint16_t sub) override {
    Serial.printf("%10lu SUBSCRIBE %s = %u\n", millis(), c->getUUID().toString().c_str(), sub);
  }
#endif
};

#if defined(CONFIG_BLUEDROID_ENABLED)
class CccdCB : public BLEDescriptorCallbacks {
  void onWrite(BLEDescriptor *d) override {
    Serial.printf("%10lu SUBSCRIBE ffa2 cccd=%02x %02x\n", millis(), d->getValue()[0], d->getValue()[1]);
  }
};
#endif

void setup() {
  Serial.begin(115200);
  delay(1500);  // give a USB-CDC host time to attach
#if SPOOF_CAR_MAC
  // Only the base MAC must be unicast; a per-interface BT address may be anything (0x25 has bit 0 set).
  Serial.printf("set BT MAC: %s\n", esp_err_to_name(esp_iface_mac_addr_set(CAR_MAC, ESP_MAC_BT)));
#endif
  BLEDevice::init("powerbox");
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());
  BLEService *svc = server->createService(SVC);
  chNt = svc->createCharacteristic(CH_NT, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  chWr = svc->createCharacteristic(CH_WR, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
#if defined(CONFIG_BLUEDROID_ENABLED)
  BLE2902 *cccd = new BLE2902();
  cccd->setCallbacks(new CccdCB());
  chNt->addDescriptor(cccd);
#endif  // NimBLE adds the CCCD by itself
  uint8_t zero[4] = {0, 0, 0, 0};
  chNt->setValue(zero, sizeof zero);  // the real car reads 00 00 00 00
  CharCB *cb = new CharCB();
  chNt->setCallbacks(cb);
  chWr->setCallbacks(cb);
  svc->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  BLEAdvertisementData ad, sr;
  ad.setFlags(0x05);  // same flags as the car: LE limited discoverable, no BR/EDR
  ad.setName("powerbox");
  sr.setName("powerbox");
  adv->setAdvertisementData(ad);
  adv->setScanResponseData(sr);
  BLEDevice::startAdvertising();
  Serial.printf("\npowerbox_sniffer ready, advertising as \"powerbox\" from %s\n",
                BLEDevice::getAddress().toString().c_str());
  Serial.println("Switch the real car OFF, then switch the remote on and press buttons. 'x' = stop advertising, 'a' = resume.");
}

void loop() {
  static uint32_t t;
  if (millis() - t > 10000) { t = millis(); Serial.printf("%10lu alive\n", millis()); }
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'x') { BLEDevice::stopAdvertising(); Serial.println("advertising OFF"); }
    if (c == 'a') { BLEDevice::startAdvertising(); Serial.println("advertising ON"); }
  }
  delay(20);
}
