# LEGO motor controller

Browser controller for LEGO-compatible Bluetooth motors, several at once:

- **XC-6 "POWERPACK" motor** (XP Block / 积木Program app), advertises as `JG_JMC-xxxx`
- **"powerbox" mecanum car** (Power Box app, "M Serial"), gray brick chassis with 4 mecanum wheels

One HTML file, nothing to install: the page talks to the devices directly through Web Bluetooth.
Both protocols were decoded from the vendor apps and checked on the real hardware. See [PROTOCOL.md](PROTOCOL.md).

## Use

1. Open `index.html` in **Chrome or Edge**. Firefox and Safari have no Web Bluetooth.
   Opening the file directly works; `python -m http.server 8553` in this folder serves it at
   http://127.0.0.1:8553/ as well.
2. Switch the device on and **close the vendor app**: a device accepts one connection at a time.
   While the browser is connected, the car ignores its own remote.
3. Click **+ Add device** and pick `JG_JMC-…` or `powerbox`. Repeat for each device; each gets a card.

`index.html?sim` runs against simulated devices (every second one is a car) for UI work without hardware.

## Controls

**Motor:** − / Stop / + in 10 % steps, a −100…+100 % slider (optionally springing back to 0),
and ◀ / ▶ for full speed while held.

**Car:**

- **8-way pad**: ↑ ↓ drive, ← → strafe, and the four diagonals, which drive only one pair of opposite wheels
  (front-left + rear-right, or front-right + rear-left). Hold a button to move; release to stop.
- **spin left / spin right**: rotate in place.
- **joystick**: analog driving in any direction; the **turn** slider adds rotation while driving.
- **speed**: limits all of the above.
- the wheel display shows what each wheel is doing.

| key | action |
|---|---|
| `Space` | stop everything |
| `1`–`9` | select a device card |
| `↑` / `↓` | selected motor ±10 % |
| `W A S D` (and combinations for diagonals) | drive the selected car |
| `Q` / `E` | spin the selected car |

Everything stops when the window loses focus, when the page closes, and before a disconnect.
**Settings** on each card: a name, invert switches per motor/wheel, and for the car which motor port drives
which wheel plus "swap left/right" (defaults match the tested car).

## Files

- `index.html`: the controller
- `PROTOCOL.md`: both protocols, what is confirmed and how it was found
- `tools/`: the reverse-engineering kit used along the way: HCI log decoders (`btsnoop.py`, `btsnoop_adv.py`,
  `btsnooz.py`), BLE scanners (`ble_scan.py`, `ble_watch.py`), adb drivers for the vendor apps, `powerbox_test.py`
  (drives the car from Python with bleak), and `mk/` (Mould King advertising encoder/decoder)
- `firmware/`: ESP32 helpers used during the hunt (fake car / fake motor GATT servers, BLE central catcher,
  advertising broadcaster)
