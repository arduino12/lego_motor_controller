"""Parse an Android btsnoop_hci.log and print ATT traffic.
Usage: btsnoop.py file [--all] [--since SECONDS]
"""
import struct, sys, datetime, collections

path = sys.argv[1]
show_all = '--all' in sys.argv
data = open(path, 'rb').read()
assert data[:8] == b'btsnoop\0', 'not a btsnoop file'
off = 16
EPOCH_DELTA = 0x00dcddb30f2f8000  # µs from 0 AD to 1970
frag = {}
handles = {}           # conn handle -> peer address
rows = []
OPS = {0x52: 'WCMD', 0x12: 'WREQ', 0x13: 'WRSP', 0x1b: 'NTF', 0x1d: 'IND', 0x0a: 'RREQ', 0x0b: 'RRSP',
       0x08: 'RBT_REQ', 0x09: 'RBT_RSP', 0x10: 'RBG_REQ', 0x11: 'RBG_RSP', 0x04: 'FIND_REQ', 0x05: 'FIND_RSP',
       0x02: 'MTU_REQ', 0x03: 'MTU_RSP', 0x01: 'ERR'}
while off + 24 <= len(data):
    olen, ilen, flags, drops, ts = struct.unpack('>IIIIq', data[off:off + 24])
    pkt = data[off + 24: off + 24 + ilen]
    off += 24 + ilen
    t = datetime.datetime(1970, 1, 1) + datetime.timedelta(microseconds=ts - EPOCH_DELTA)
    rx = flags & 1
    if not pkt:
        continue
    typ = pkt[0]
    if typ == 0x04 and len(pkt) > 3 and pkt[1] == 0x3e and pkt[3] == 0x01:   # LE connection complete
        status, h = pkt[4], struct.unpack('<H', pkt[5:7])[0]
        addr = ':'.join(f'{b:02x}' for b in reversed(pkt[9:15]))
        handles[h] = addr
        rows.append((t, 'EVT', f'LE conn complete status={status} handle={h:#x} peer={addr}'))
        continue
    if typ == 0x01 and len(pkt) > 3:   # HCI command
        opc = struct.unpack('<H', pkt[1:3])[0]
        if opc in (0x2008, 0x2009):    # LE set adv / scan resp data
            rows.append((t, 'CMD', f'{"ADV" if opc == 0x2008 else "SCANRSP"} data {pkt[4:].hex(" ")}'))
        continue
    if typ != 0x02:
        continue
    hf, ln = struct.unpack('<HH', pkt[1:5])
    h, pb = hf & 0x0fff, (hf >> 12) & 3
    body = pkt[5:5 + ln]
    key = (h, rx)
    if pb == 1:
        frag[key] = frag.get(key, b'') + body
    else:
        frag[key] = body
    buf = frag[key]
    if len(buf) < 4:
        continue
    l2len, cid = struct.unpack('<HH', buf[:4])
    if len(buf) - 4 < l2len:
        continue
    att = buf[4:4 + l2len]
    frag[key] = b''
    if cid != 4 or not att:
        continue
    op = att[0]
    name = OPS.get(op, f'op{op:02x}')
    if op in (0x52, 0x12, 0x1b, 0x1d):
        handle = struct.unpack('<H', att[1:3])[0]
        rows.append((t, ('RX ' if rx else 'TX ') + name, f'h={handle:#06x} {att[3:].hex(" ")}'))
    elif show_all:
        rows.append((t, ('RX ' if rx else 'TX ') + name, att[1:].hex(' ')))

for t, k, v in rows:
    print(f'{t:%H:%M:%S.%f}'[:-3], k.ljust(8), v)

print('\n== distinct writes per handle')
c = collections.Counter(v for t, k, v in rows if k.startswith('TX W'))
for v, n in c.most_common(60):
    print(f'{n:5d}  {v}')
