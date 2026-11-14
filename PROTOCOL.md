# XP Block / 积木Program BLE protocol

Covers the **XC-6 "POWERPACK"** single motor (battery + Bluetooth, one output shaft, advertises as
`JG_JMC-xxxx`) and the app's **XC-7** 6-channel page. The gray **"powerbox"** mecanum car is a different
product and is not mapped (see below).

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

## XC-7 page (6-channel remote) — confirmed

Captured with an ESP32 posing as an XC-6 motor (`firmware/powerbox_sniffer`, env `esp32dev-motor`) while
`tools/drive_xc7.py` moved each control on the app's XC-7 page through adb. Same frame, 8-byte payload:

```
payload = [j1 dir, j1 strength, j2 dir, j2 strength, 01, slider dir, E strength, F strength]
```

| control (screen in landscape) | dir byte | dir bits | strength byte |
|---|---|---|---|
| left joystick, vertical axis **A** | 0 | `01` up, `02` down | 1 |
| left joystick, horizontal axis **B** | 0 | `04` left, `08` right | 1 |
| right joystick, vertical axis **C** | 2 | `01` up, `02` down | 3 |
| right joystick, horizontal axis **D** | 2 | `04` left, `08` right | 3 |
| slider **E** | 5 | `01` left, `02` right | 6 |
| slider **F** | 5 | `04` left, `08` right | 7 |

Diagonals OR the bits (`05`, `06`, `09`, `0a`); strength rises 0 → `ff` with the throw. The app streams a frame
about every 100 ms while a control moves; on release it sends the all-zero frame
`5a 6b 02 00 08 00 00 00 00 01 00 00 00 d0` five times.

## "powerbox" mecanum car — not mapped

Gray brick chassis, 4 mecanum wheels, own 2.4 GHz remote, no app. Advertises `02 01 05 09 09 "powerbox"` from
public address `25:02:00:00:1c:43`. GATT: `0000ffa0-0002-1000-8000-00805f9b34fb` (note `-0002-`), with
`ffa2` read+notify (reads `00 00 00 00`) and `ffa1` write; the generic `1800`/`1801` services as well.

What was tried, all with the wheels in view:

- **XP Block app**: connects, then has nothing to send (it only knows `fff2`).
- **576 probe packets** on `ffa1` (`index.html` probe panel): known brick-hub protocols (LEGO PU, BuWizz,
  SBrick, Circuit Cubes), every single byte, `[cmd, speed]` pairs, per-motor 4-byte, 8/20-byte padded,
  common headers with sum/xor/length, ASCII. Every write accepted, `ffa2` never changed, no wheel moved.
  Once, during the full run, the car LED switched from solid to **fast blinking** while the BLE link stayed up:
  the firmware does parse writes. Packets 1–288 alone don't do it; 289–576 not yet bisected.
- **XC-7 frames streamed** every 100 ms for 2 s per direction/slider: nothing.
- **The remote is not BLE**: an ESP32 cloning the car exactly (name, address, advertisement bytes, service)
  got no connection; with the car's address as a BLE central it heard no directed or other advertising from the
  remote; and the car keeps advertising while paired with the remote. The remote (16-pin chip, 24 MHz
  crystal, PCB antenna, one button per pin) is a proprietary 2.4 GHz link. While a BLE central is connected
  the car refuses the remote.

## Other observations

- The APK also contains a BLE *advertiser* (`PrepareAdvertise`, manufacturer ID 2402 = `0x0962`) that nothing
  in the Java code calls.

## Capturing another model (e.g. XC-7)

1. Android phone: Developer options → enable **Bluetooth HCI snoop log**, then toggle Bluetooth off/on.
   On the LG D722 (Android 5.0.2) the log is written to `/sdcard/btsnoop_hci.log`.
2. Open the app, POWERPACK → pick the model, connect, and do one action at a time with pauses
   (or script it with `adb shell input`, like `tools/drive_xc6.py`).
3. `adb pull /sdcard/btsnoop_hci.log cap.log` (in Git Bash set `MSYS_NO_PATHCONV=1` first).
4. `python tools/btsnoop.py cap.log`: every ATT write/notification with a timestamp, plus a count of
   distinct writes.
