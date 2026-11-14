# XP Block / 积木Program BLE protocol

Covers the **XC-6 "POWERPACK"** single motor (battery + Bluetooth, one output shaft, advertises as
`JG_JMC-xxxx`). The **XC-7** gray omni car is not mapped yet.

Sources:

1. The Android app `com.smadom.xpblock` v3.1.0 (Play: "积木Program", iOS: "XP Block"), pulled from the
   phone with `adb`. It is a Flutter app; the Bluetooth glue is plain Java in
   `com.smadom.xpblock.MainActivity` and `com.example.bluetoothlibrary`, read with androguard
   (`tools/dump_classes.py`).
2. Android Bluetooth HCI snoop logs captured while `adb input` drove the XC-6 page one action at a time
   (`tools/drive_xc6.py`, decoded with `tools/btsnoop.py`).
3. Checked from desktop Chrome (Windows 11, Intel Bluetooth) with two motors at once:
   JG_JMC-6934 and JG_JMC-C334, 2026-11-14.

## Link layer — confirmed

| item | value |
|---|---|
| advertised name | `JG_JMC-` + 4 hex digits, **padded with trailing spaces** (the app filters its scan on the prefix `JG_JMC-`) |
| service | `0000fff0-0000-1000-8000-00805f9b34fb` |
| `fff1` | read, notify: motor → phone status |
| `fff2` | **write with response only** (properties `0x08`): phone → motor commands |
| handshake | none. The app writes commands right after connecting. Status notifications arrive even before the CCCD is written. |
| connections | one central at a time; close the phone app before connecting from the browser |
| Windows | Chrome connects without pairing the motor in Windows Settings |

## Frame — confirmed

```
5a 6b  TT  00  NN  <NN payload bytes>  SS
│      │   │   │                       └ checksum = (sum of all preceding bytes) & 0xff
│      │   │   └ payload length
│      │   └ always 00
│      └ type: 02 = command (phone → motor), 01 = status (motor → phone)
└ sync
```

The checksum rule matches every captured frame (~150 frames, both directions).

## XC-6 motor command — type `02`, 5-byte payload

```
payload = [dir, speed, dir, 00, 01]
```

| byte | meaning | status |
|---|---|---|
| 0 `dir` | `01` forward (app "+" / slider up), `02` reverse (app "−" / slider down), `00` stop | confirmed |
| 1 `speed` | 0–255, linear. The app's +/− buttons step 10 %: `19`, `33`, `4c` …; slider at the end = `ff` | confirmed |
| 2 | always equal to byte 0 | copied verbatim, meaning unknown |
| 3, 4 | always `00 01` | copied verbatim, meaning unknown |

| action | frame |
|---|---|
| forward 10 % | `5a 6b 02 00 05 01 19 01 00 01 e8` |
| forward 100 % | `5a 6b 02 00 05 01 ff 01 00 01 ce` |
| reverse 30 % | `5a 6b 02 00 05 02 4c 02 00 01 1d` |
| stop | `5a 6b 02 00 05 00 00 00 00 01 cd` |

App behaviour (confirmed from captures):

- A frame is sent only when the value changes: once per +/− tap, and about every 120 ms while the slider moves.
  There is no keep-alive, and the motor holds the last speed.
- Stop (button, or the slider springing back on release) is the stop frame sent **5 times**.
- The six sound/effect buttons on the XC-6 page send nothing to the motor. The sounds play on the phone.

## Status — type `01`, 1-byte payload

`5a 6b 01 00 01 64 2b` arrives on `fff1` every 2 s. The payload `0x64` = 100 is **assumed** to be battery %:
only 100 has been observed so far (fresh batteries).

## Other observations

- With the same motor connected, a different model page in the app sent 8-byte payloads, e.g.
  `5a 6b 02 00 08 02 2b 00 00 01 00 00 00 fd` and `… 09 b8 00 00 01 00 00 00 …`. Which model
  page that was is unknown, and so is the layout. The page does not use it.
- The APK also contains a BLE *advertiser* (`PrepareAdvertise`, manufacturer ID 2402 = `0x0962`, payload
  built in Dart). XC-6 does not use it. If XC-7 or another model turns out to be advertisement-controlled,
  a browser cannot drive it directly: Web Bluetooth cannot advertise, so it would need a small
  ESP32 bridge over Web Serial.

## Open

- Meaning of payload bytes 2–4 (a second channel? LED?).
- Whether the status byte really is battery % (watch it as the batteries drain).
- Whether the motor stops on its own when the link drops. The page sends stop on blur, unload and
  disconnect, so the browser side doesn't depend on it.
- **XC-7 car**: capture it the same way (see below).

## Capturing another model (e.g. XC-7)

1. Android phone: Developer options → enable **Bluetooth HCI snoop log**, then toggle Bluetooth off/on.
   On the LG D722 (Android 5.0.2) the log is written to `/sdcard/btsnoop_hci.log`.
2. Open the app, POWERPACK → pick the model, connect, and do one action at a time with pauses
   (or script it with `adb shell input`, like `tools/drive_xc6.py`).
3. `adb pull /sdcard/btsnoop_hci.log cap.log` (in Git Bash set `MSYS_NO_PATHCONV=1` first).
4. `python tools/btsnoop.py cap.log`: every ATT write/notification with a timestamp, plus a count of
   distinct writes.
