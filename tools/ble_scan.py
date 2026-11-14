"""Scan BLE advertisements from this PC (Windows/WinRT via bleak) and print every distinct device.
Usage: ble_scan.py [seconds] [--all]   (default 12 s; without --all, nameless devices with no
manufacturer/service data are hidden)"""
import asyncio, sys
from bleak import BleakScanner

secs = float(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else 12
show_all = '--all' in sys.argv
seen = {}


def cb(dev, adv):
    key = dev.address
    first = key not in seen
    seen[key] = (dev, adv)
    if first and (show_all or adv.local_name or adv.manufacturer_data or adv.service_uuids or adv.service_data):
        mfr = ' '.join(f'mfr[{k:#06x}]={v.hex(" ")}' for k, v in adv.manufacturer_data.items())
        svc = ' '.join(adv.service_uuids)
        sd = ' '.join(f'sd[{k[4:8]}]={v.hex(" ")}' for k, v in adv.service_data.items())
        print(f'{dev.address}  rssi={adv.rssi:<4} name={adv.local_name!r:24} {mfr} {svc} {sd}', flush=True)


async def main():
    async with BleakScanner(cb, scanning_mode='active'):
        await asyncio.sleep(secs)
    print(f'-- {len(seen)} devices in {secs:.0f} s')

asyncio.run(main())
