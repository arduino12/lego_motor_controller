"""Print every BLE advertisement from nearby devices (RSSI above a threshold) whenever its payload changes.
For finding broadcast-only remotes: run it, press buttons one at a time, see which device's data changes.
Usage: ble_watch.py [seconds=30] [min_rssi=-65] [out.txt]"""
import asyncio, sys, time
from bleak import BleakScanner

secs = float(sys.argv[1]) if len(sys.argv) > 1 else 30
min_rssi = int(sys.argv[2]) if len(sys.argv) > 2 else -65
out = open(sys.argv[3], 'a', encoding='utf-8', buffering=1) if len(sys.argv) > 3 else None
last = {}
t0 = time.time()


def fmt(adv):
    parts = []
    if adv.local_name:
        parts.append(f'name={adv.local_name!r}')
    parts += [f'mfr[{k:#06x}]={v.hex(" ")}' for k, v in adv.manufacturer_data.items()]
    parts += [f'sd[{k[4:8]}]={v.hex(" ")}' for k, v in adv.service_data.items()]
    parts += [f'uuid={u}' for u in adv.service_uuids]
    return ' '.join(parts) or '(empty)'


def cb(dev, adv):
    if adv.rssi < min_rssi:
        return
    s = fmt(adv)
    if last.get(dev.address) == s:
        return
    last[dev.address] = s
    line = f'{time.time() - t0:7.2f}s {dev.address} rssi={adv.rssi:<4} {s}'
    print(line, flush=True)
    if out:
        out.write(line + '\n')


async def main():
    async with BleakScanner(cb, scanning_mode='active'):
        await asyncio.sleep(secs)
    print(f'-- done, {len(last)} devices above {min_rssi} dBm')

asyncio.run(main())
