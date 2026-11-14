"""Try Mould King MK6 / MK4 advertising telegrams on a car via the mk_broadcaster ESP32.
Usage: mk_try.py COM7 [variant ...]   variants: mk6-ae18 mk6-7ba7 mk4-ae18 mk4-7ba7 (default: all)
Each step prints a big label; watch the car's LED (bind) and wheels."""
import sys, time, datetime
import serial
from mkcrypt import encode

port = sys.argv[1]
variants = sys.argv[2:] or ['mk6-ae18', 'mk6-7ba7', 'mk4-ae18', 'mk4-7ba7']
s = serial.Serial(port, 115200, timeout=0.2)
time.sleep(2.5)          # board resets when the port opens
s.reset_input_buffer()


def send(raw_hex):
    s.write(f'D {encode(raw_hex).hex()}\n'.encode())


def hold(label, raw_hex, secs):
    print(f'{datetime.datetime.now():%H:%M:%S}  >>> {label:<34} raw {raw_hex}', flush=True)
    end = time.time() + secs
    while time.time() < end:
        send(raw_hex)            # the ESP32 advertises continuously; resend ~10/s like the app
        time.sleep(0.1)


def mk6(k):
    hdr = '61'
    neutral = ['80'] * 6
    hold(f'{k}: BIND (device 0)', f'6d{k}80808080' + '92', 3)
    for ch in range(6):
        for val, d in (('ff', '+'), ('00', '-')):
            c = neutral.copy(); c[ch] = val
            hold(f'{k}: channel {ch} {d}', hdr + k + ''.join(c) + '9e', 1.5)
    hold(f'{k}: stop', hdr + k + ''.join(neutral) + '9e', 1)


def mk4(k):
    hold(f'{k}: BIND (MK4 shared connect)', f'ad{k}808080f352', 3)
    for ch in range(4):              # slot 0, channels 0..3
        for nib, d in ((0xF, '+'), (0x1, '-')):
            nibbles = [8] * 12
            nibbles[ch] = nib
            raw = ''.join(f'{nibbles[2 * i]:x}{nibbles[2 * i + 1]:x}' for i in range(6))
            hold(f'{k}: slot0 ch{ch} {d}', f'7d{k}{raw}82', 1.5)
    hold(f'{k}: stop', f'7d{k}888888888888' + '82', 1)


try:
    for v in variants:
        fam, k = v.split('-')
        print(f'\n===== {v} =====', flush=True)
        (mk6 if fam == 'mk6' else mk4)(k)
finally:
    s.write(b'S\n')
    print('\nstopped advertising', flush=True)
