"""Drive the "powerbox" mecanum car from the PC with the frame captured from the Power Box app ("M Serial").
Frame (16 bytes) to ffa1, repeated every 100 ms:  fc 0f 01 [A] [B] [C] [D] 00*8 [sum8]
motor byte: bit 7 = direction, bits 0-6 = speed 0..127 (0 = stop).
Usage: powerbox_test.py [address] [slow]   (default 25:02:00:00:1C:43; slow = forward only, 3 s each)"""
import asyncio, sys, time
from bleak import BleakClient

ADDR = next((a for a in sys.argv[1:] if ':' in a), '25:02:00:00:1C:43')
WR = '0000ffa1-0002-1000-8000-00805f9b34fb'
NT = '0000ffa2-0002-1000-8000-00805f9b34fb'


def frame(a=0, b=0, c=0, d=0):
    def enc(v):                      # -127..127 -> sign-magnitude byte
        v = max(-127, min(127, int(v)))
        return (0x80 | -v) if v < 0 else v
    f = [0xfc, 0x0f, 0x01, enc(a), enc(b), enc(c), enc(d)] + [0] * 8
    return bytes(f + [sum(f) & 0xff])


async def stream(cl, f, secs, label):
    print(f'{time.strftime("%H:%M:%S")}  >>> {label:<14} {f.hex(" ")}', flush=True)
    end = time.time() + secs
    while time.time() < end:
        await cl.write_gatt_char(WR, f, response=True)
        await asyncio.sleep(0.1)


async def main():
    assert frame().hex() == 'fc0f010000000000000000000000000c'
    assert frame(c=0x67).hex() == 'fc0f010000670000000000000000' + '0073'
    async with BleakClient(ADDR, timeout=20) as cl:
        print('connected', flush=True)
        await cl.start_notify(NT, lambda h, d: print('   notify', d.hex(' '), flush=True))
        await stream(cl, frame(), 1.5, 'stop')
        slow = 'slow' in sys.argv
        for i, name in enumerate('ABCD'):
            for sign, dname in ((1, 'fwd'),) if slow else ((1, 'fwd'), (-1, 'rev')):
                sp = [0, 0, 0, 0]; sp[i] = sign * 100
                await stream(cl, frame(*sp), 3 if slow else 1.5, f'motor {name} {dname}')
                await stream(cl, frame(), 2 if slow else 0.8, 'stop')
        await stream(cl, frame(), 1, 'stop')
    print('done', flush=True)

asyncio.run(main())
