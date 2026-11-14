# LEGO motor controller

Browser controller for the XP Block / 积木Program LEGO-compatible Bluetooth motors (the **XC-6 POWERPACK**
single motor, advertising as `JG_JMC-xxxx`). One HTML file, nothing to install: the page talks to the
motors directly through Web Bluetooth and drives several at once.

The protocol was decoded from the vendor Android app and checked on two real motors at once. See
[PROTOCOL.md](PROTOCOL.md).

## Use

1. Open `index.html` in **Chrome or Edge**. Firefox and Safari have no Web Bluetooth.
   Opening the file directly works; `python -m http.server 8553` in this folder serves it at
   http://127.0.0.1:8553/ as well.
2. Switch the motor on and **close the phone app**: a motor accepts only one connection.
3. Click **+ Add motor** and pick `JG_JMC-…`. Repeat for each motor; every motor gets its own card.
   **+ Add (show all)** lists every nearby BLE device, in case a motor doesn't show up.

`index.html?sim` runs against simulated motors for UI work without hardware.

## Controls

Each motor card has:

- **− / Stop / +**: speed in 10 % steps, like the app
- a **slider** from −100 % to +100 % (optionally springing back to 0 on release)
- **◀ / ▶**: full speed while held
- **Advanced**: a friendly name, an invert-direction switch, the GATT map, and a raw-hex sender
  (the checksum is appended when missing)

| key | action |
|---|---|
| `Space` | stop all motors |
| `1`–`9` | select a motor card |
| `↑` / `↓` | selected motor ±10 % |
| `W A S D`, `Q E` | drive the XC-7 car (once it is mapped) |

All motors stop when the window loses focus, when the page closes, and before a disconnect.
Names, invert switches and the model choice are remembered per motor.

The log shows every frame sent (TX) and, optionally, the motors' status frames (RX). **Save**
downloads it as a text file.

## Status

- **XC-6 motor**: working, tested with two motors at once.
- **XC-7 gray omni car** (4 motors, 4 omni wheels): the card and joystick exist, but the protocol is not captured yet,
  so nothing is sent.

## Files

- `index.html`: the controller
- `PROTOCOL.md`: the decoded protocol, split into confirmed, assumed and open
- `tools/btsnoop.py`: decodes an Android `btsnoop_hci.log` into ATT writes and notifications
- `tools/dump_classes.py`: disassembles chosen APK classes with androguard
- `tools/drive_xc6.py`: taps the vendor app's XC-6 page through `adb` one action at a time (screen coordinates for an LG D722)
