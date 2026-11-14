// powerbox_sniffer: a fake BLE peripheral that prints every write it receives.
//
// FAKE_MOTOR=0 (default): pretends to be the "powerbox" mecanum car (name, address, flags, service
//   ffa0 with read/notify ffa2 and write ffa1 on the non-standard -0002- base), to catch its remote.
// FAKE_MOTOR=1: pretends to be an XP Block XC-6 motor ("JG_JMC-…", service fff0, notify fff1, write
//   fff2, status frame every 2 s), so the XP Block app connects and we can read what any of its pages
//   (e.g. XC-7) sends.
//
// Uses the BLE library bundled with Arduino-ESP32 core 3.x, which runs on Bluedroid (classic ESP32)
// or NimBLE (ESP32-C3/S3): both are handled below. Serial: 'x' stop advertising, 'a' advertise again.
#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <esp_mac.h>
#if defined(CONFIG_BLUEDROID_ENABLED)
#include <BLE2902.h>
#endif

#ifndef FAKE_MOTOR
#define FAKE_MOTOR 0
#endif

#if FAKE_MOTOR
static const char *NAME  = "JG_JMC-FAKE";
static const char *SVC   = "0000fff0-0000-1000-8000-00805f9b34fb";
static const char *CH_NT = "0000fff1-0000-1000-8000-00805f9b34fb";
static const char *CH_WR = "0000fff2-0000-1000-8000-00805f9b34fb";
#define SPOOF_CAR_MAC 0
#else
static const char *NAME  = "powerbox";
static const char *SVC   = "0000ffa0-0002-1000-8000-00805f9b34fb";
static const char *CH_NT = "0000ffa2-0002-1000-8000-00805f9b34fb";
static const char *CH_WR = "0000ffa1-0002-1000-8000-00805f9b34fb";
// Take over the real car's public address, in case the remote is locked to it.
#define SPOOF_CAR_MAC 1
#endif
static const uint8_t CAR_MAC[6] = {0x25, 0x02, 0x00, 0x00, 0x1c, 0x43};

static BLECharacteristic *chWr, *chNt;
static bool connected;
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
  void onConnect(BLEServer *s, esp_ble_gatts_cb_param_t *p) override { connected = true; printPeer(p->connect.remote_bda); }
#else
  void onConnect(BLEServer *s, ble_gap_conn_desc *d) override {
    const uint8_t *a = d->peer_ota_addr.val;  // little-endian in NimBLE
    uint8_t m[6] = {a[5], a[4], a[3], a[2], a[1], a[0]};
    connected = true;
    printPeer(m);
  }
#endif
  void onDisconnect(BLEServer *s) override {
    connected = false;
    flushRepeats();
    Serial.printf("%10lu DISCONNECT\n", millis());
    delay(100);
    BLEDevice::startAdvertising();
  }
};

class CharCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String line = c == chWr ? "W wr" : "W nt";
    size_t n = c->getLength();
    const uint8_t *d = c->getData();
    line += " len=" + String(n) + ":";
    char b[4];
    for (size_t i = 0; i < n; i++) { snprintf(b, sizeof b, " %02x", d[i]); line += b; }
    if (line == last && millis() - lastAt < 1000) { repeats++; lastAt = millis(); return; }  // fold repeats
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
    Serial.printf("%10lu SUBSCRIBE cccd=%02x %02x\n", millis(), d->getValue()[0], d->getValue()[1]);
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
  BLEDevice::init(NAME);
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
#if FAKE_MOTOR
  static uint8_t status[7] = {0x5a, 0x6b, 0x01, 0x00, 0x01, 0x64, 0x2b};  // what a real XC-6 motor reports
  chNt->setValue(status, sizeof status);
#else
  uint8_t zero[4] = {0, 0, 0, 0};
  chNt->setValue(zero, sizeof zero);  // the real car reads 00 00 00 00
#endif
  CharCB *cb = new CharCB();
  chNt->setCallbacks(cb);
  chWr->setCallbacks(cb);
  svc->start();

  BLEAdvertising *adv = BLEDevice::getAdvertising();
  BLEAdvertisementData ad, sr;
  ad.setFlags(0x05);  // both real devices use flags 05: LE limited discoverable, no BR/EDR
  ad.setName(NAME);
#if FAKE_MOTOR
  ad.setCompleteServices(BLEUUID((uint16_t)0xfff0));  // the motor advertises fff0
#endif
  sr.setName(NAME);
  adv->setAdvertisementData(ad);
  adv->setScanResponseData(sr);
  BLEDevice::startAdvertising();
  Serial.printf("\n%s ready, advertising as \"%s\" from %s\n", FAKE_MOTOR ? "fake XC-6 motor" : "fake powerbox car",
                NAME, BLEDevice::getAddress().toString().c_str());
}

void loop() {
  static uint32_t t, tn;
  if (millis() - t > 10000) { t = millis(); Serial.printf("%10lu alive%s\n", millis(), connected ? " (connected)" : ""); }
#if FAKE_MOTOR
  if (connected && millis() - tn > 2000) { tn = millis(); chNt->notify(); }  // status every 2 s, like the motor
#endif
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'x') { BLEDevice::stopAdvertising(); Serial.println("advertising OFF"); }
    if (c == 'a') { BLEDevice::startAdvertising(); Serial.println("advertising ON"); }
  }
  delay(20);
}
