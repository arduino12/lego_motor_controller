"""List BLE advertisements seen in an Android btsnoop_hci.log, one line per distinct (address, payload).
Usage: btsnoop_adv.py file [name-or-address-substring]
Also lists what the phone itself advertised (HCI LE Set Advertising Data)."""
import struct, sys, datetime, collections

path = sys.argv[1]
flt = sys.argv[2].lower() if len(sys.argv) > 2 else ''
data = open(path, 'rb').read()
assert data[:8] == b'btsnoop\0'
EPOCH_DELTA = 0x00dcddb30f2f8000
off = 16


def ad_fields(b):
    out, i = [], 0
    while i < len(b):
        ln = b[i]
        if ln == 0 or i + 1 + ln > len(b):
            break
        out.append((b[i + 1], b[i + 2:i + 1 + ln]))
        i += 1 + ln
    return out


def describe(adv):
    parts, name = [], ''
    for t, v in ad_fields(adv):
        if t in (0x08, 0x09):
            name = v.decode('latin1')
            parts.append(f'name="{name}"')
        elif t == 0xff:
            parts.append(f'mfr[{struct.unpack("<H", v[:2])[0]:#06x}]={v[2:].hex(" ")}')
        elif t in (0x02, 0x03):
            parts.append('uuid16=' + ','.join(f'{u:04x}' for u in struct.unpack(f'<{len(v)//2}H', v)))
        elif t in (0x06, 0x07):
            parts.append('uuid128=' + v[::-1].hex())
        elif t == 0x16:
            parts.append(f'svcdata[{struct.unpack("<H", v[:2])[0]:04x}]={v[2:].hex(" ")}')
        elif t == 0x01:
            parts.append(f'flags={v.hex()}')
        else:
            parts.append(f'ad{t:02x}={v.hex(" ")}')
    return name, ' '.join(parts)


seen = collections.OrderedDict()
own = collections.OrderedDict()
while off + 24 <= len(data):
    olen, ilen, flags, drops, ts = struct.unpack('>IIIIq', data[off:off + 24])
    pkt = data[off + 24: off + 24 + ilen]
    off += 24 + ilen
    t = datetime.datetime(1970, 1, 1) + datetime.timedelta(microseconds=ts - EPOCH_DELTA)
    if len(pkt) > 4 and pkt[0] == 0x01 and struct.unpack('<H', pkt[1:3])[0] in (0x2008, 0x2009):
        n = pkt[4]
        _, d = describe(pkt[5:5 + n])
        k = d
        if k not in own:
            own[k] = [t, t, 0]
        own[k][1] = t; own[k][2] += 1
        continue
    if len(pkt) > 4 and pkt[0] == 0x04 and pkt[1] == 0x3e and pkt[3] == 0x02:
        num, i = pkt[4], 5
        for _ in range(num):
            if i + 9 > len(pkt):
                break
            evt, atype = pkt[i], pkt[i + 1]
            addr = ':'.join(f'{b:02x}' for b in reversed(pkt[i + 2:i + 8]))
            dl = pkt[i + 8]
            adv = pkt[i + 9:i + 9 + dl]
            rssi = struct.unpack('b', pkt[i + 9 + dl:i + 10 + dl])[0] if i + 9 + dl < len(pkt) else 0
            i += 10 + dl
            name, d = describe(adv)
            if flt and flt not in d.lower() and flt not in addr:
                continue
            k = (addr, evt, d)
            if k not in seen:
                seen[k] = [t, t, 0, rssi]
            seen[k][1] = t; seen[k][2] += 1; seen[k][3] = rssi

EVT = {0: 'ADV_IND', 1: 'DIRECT', 2: 'SCAN_IND', 3: 'NONCONN', 4: 'SCAN_RSP'}
for (addr, evt, d), (t1, t2, n, rssi) in seen.items():
    print(f'{t1:%H:%M:%S}-{t2:%H:%M:%S} n={n:<4} {addr} {EVT.get(evt, evt):8} rssi={rssi:<4} {d}')
if own:
    print('\n== phone advertised')
    for d, (t1, t2, n) in own.items():
        print(f'{t1:%H:%M:%S}-{t2:%H:%M:%S} n={n:<4} {d}')
