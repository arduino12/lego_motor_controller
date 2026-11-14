"""List the Mould King style (company 0xFFF0) adverts a phone transmitted, decoded, from a btsnoop log.
Finds HCI LE Set Advertising Data (0x2008), LE Set Extended Advertising Data (0x2037) and the vendor
multi-advertising command 0xFD54 / sub 0x02 (Broadcom/Qualcomm, Android 5-9).
Usage: snoop_mk.py btsnoop.log"""
import struct, sys, datetime, os
sys.path.insert(0, os.path.dirname(__file__))
from mkcrypt import decode

EPOCH = 0x00dcddb30f2f8000
data = open(sys.argv[1], 'rb').read()
off, last, rows = 16, None, []


def ad_fields(b):
    i = 0
    while i < len(b) and b[i]:
        yield b[i + 1], b[i + 2:i + 1 + b[i]]
        i += 1 + b[i]


while off + 24 <= len(data):
    olen, ilen, flags, drops, ts = struct.unpack('>IIIIq', data[off:off + 24])
    pkt = data[off + 24:off + 24 + ilen]
    off += 24 + ilen
    if len(pkt) < 4 or pkt[0] != 0x01:
        continue
    op = struct.unpack('<H', pkt[1:3])[0]
    p = pkt[4:]
    adv = None
    if op == 0x2008:
        adv = p[1:1 + p[0]]
    elif op == 0x2037:
        adv = p[4:4 + p[3]]
    elif op == 0xFD54 and p and p[0] == 0x02:
        adv = p[2:2 + p[1]]
    if not adv:
        continue
    for t, v in ad_fields(adv):
        if t == 0xFF and v[:2] == b'\xf0\xff':
            raw, ok = decode(v[2:])
            when = datetime.datetime(1970, 1, 1) + datetime.timedelta(microseconds=ts - EPOCH)
            rows.append((when, raw.hex(' '), ok))

prev, n = None, 0
for when, raw, ok in rows:
    if raw == prev:
        n += 1
        continue
    if n:
        print(f'{"":15} (x{n} repeats)')
    print(f'{when:%H:%M:%S.%f}'[:-3], raw, '' if ok else '  CRC MISMATCH')
    prev, n = raw, 0
if n:
    print(f'{"":15} (x{n} repeats)')
print(f'-- {len(rows)} adverts, {len(set(r[1] for r in rows))} distinct')
