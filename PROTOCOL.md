# BLE protocols: XP Block XC-6 motor and "powerbox" mecanum car

Covers the **XC-6 "POWERPACK"** single motor (battery + Bluetooth, one output shaft, advertises as
`JG_JMC-xxxx`), the XP Block app's **XC-7** 6-channel page, and the gray **"powerbox"** mecanum car
(a different product with its own app, see its section).

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

## "powerbox" mecanum car — confirmed

Gray brick chassis, 4 mecanum wheels, its own 2.4 GHz remote. Vendor app: **"Power Box"**
(`com.yundongjia.app.blocks_powerbox` v2.1.4, Shenzhen Yundongjia), model **"M Serial"**. The XP Block and
MK tech apps do not know it.

| item | value |
|---|---|
| advertised name | `powerbox`, public address `25:02:00:00:1c:43`, advertising `02 01 05 09 09 "powerbox"` |
| service | `0000ffa0-0002-1000-8000-00805f9b34fb` (note the **`-0002-`**, not the standard 16-bit base) |
| `ffa1` | write (with response): commands |
| `ffa2` | read + notify; reads `00 00 00 00`, never notified in any capture |
| pairing | the app bonds, but the car also obeys an unpaired connection (Web Bluetooth, bleak) |

**Command, 16 bytes, written to `ffa1` every 100 ms** (the app streams it continuously, also at rest):

```
fc 0f 01  A  B  C  D  00 00 00 00 00 00 00 00  sum
│         └──┴──┴──┴─ motor ports A-D: bit 7 = reverse, bits 0-6 = speed 0..127
└ fixed header                                  sum = (sum of the 15 bytes before it) & 0xff
```

| example | frame |
|---|---|
| stop | `fc 0f 01 00 00 00 00 00 00 00 00 00 00 00 00 0c` |
| port C forward 81 % | `fc 0f 01 00 00 67 00 00 00 00 00 00 00 00 00 73` |
| all four forward 100 % | `fc 0f 01 7f 7f 7f 7f 00 00 00 00 00 00 00 00 08` |
| port A reverse 50 % | `fc 0f 01 c0 00 00 00 00 00 00 00 00 00 00 00 cc` |

Wheel mapping on this car: **front-left = C, front-right = D, rear-left = A, rear-right = B**, all four turn the
car-forward way for a positive value. The rollers mirror the textbook mecanum layout, so the strafe term of the
standard mix (`FL = y+x+w, FR = y−x−w, RL = y−x+w, RR = y+x−w`) is negated. Bytes 7–14 stayed `00` in every
capture (perhaps the expansion board's two extra ports; nothing was plugged in).

Notes:

- While a BLE central is connected the car ignores its 2.4 GHz remote and holds the last motor state.
- A write longer than ~17 bytes (19 zero bytes already) makes it drop the app session: LED back to fast blink.

How it was found: everything else failed (576 probe packets, XP Block frames, Mould King broadcasts, a cloned
car for the remote). The Power Box app drove it from a Samsung Note 8 with the full Bluetooth HCI snoop log on.
On Samsung Android 9 the log is only active after Bluetooth is toggled once with the developer setting on, it
is not in `*#9900#` SysDump copies, but it is in an `adb bugreport` (`FS/data/log/bt/btsnoop_hci.log`).
`dumpsys bluetooth_manager` (`tools/btsnooz.py`) keeps HCI commands/events but drops ATT data.

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
