"""Mould King BLE-advertising telegram encoder (company id 0xFFF0), our own implementation.

Algorithm as documented by J0EK3R/mkconnect-python and jrichter24/moldqueen (both MIT):
working buffer t (len L+25): t[15..17] = 71 0f 55, t[18..22] = preamble C5..C1, both bit-reversed;
raw payload at t[23..]; CRC-16/CCITT (0x1021, init 0xffff) over the reversed preamble then the
bit-reversed payload, result bit-reversed and xor 0xffff, stored little-endian after the payload;
LFSR whitening seed 63 over t[18:], then seed 37 over all of t; on-air = t[15:15+L+10] padded to
24 bytes with filler byte[i] = i+1.

Usage:  mkcrypt.py <raw hex> ...      prints the 24-byte on-air manufacturer data for each
        mkcrypt.py --test             checks against the published test vectors
"""
import sys

PREAMBLE = bytes([0xC1, 0xC2, 0xC3, 0xC4, 0xC5])


def rev8(v):
    return int(f'{v:08b}'[::-1], 2)


def rev16(v):
    return int(f'{v:016b}'[::-1], 2)


class Lfsr:
    def __init__(self, seed):
        self.s = [1] + [(seed >> (6 - i)) & 1 for i in range(1, 7)]

    def bit(self):
        s = self.s
        r1 = s[3] ^ s[6]
        s[3], s[2], s[1], s[0] = s[2], s[1], s[0], s[6]
        s[6], s[5], s[4] = s[5], s[4], r1
        return s[0]

    def whiten(self, buf, start=0):
        for k in range(start, len(buf)):
            out = 0
            for b in range(8):
                out |= (((buf[k] >> b) & 1) ^ self.bit()) << b
            buf[k] = out


def crc16(payload):
    r = 0xFFFF
    for byte in [*reversed(PREAMBLE), *(rev8(b) for b in payload)]:
        r ^= byte << 8
        for _ in range(8):
            r = ((r << 1) ^ 0x1021 if r & 0x8000 else r << 1) & 0xFFFF
    return rev16(r) ^ 0xFFFF


def encode(raw):
    raw = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
    n = len(raw)
    t = bytearray(n + 25)
    t[15:18] = bytes([0x71, 0x0F, 0x55])
    t[18:23] = bytes(reversed(PREAMBLE))
    for i in range(15, 23):
        t[i] = rev8(t[i])
    t[23:23 + n] = raw
    c = crc16(raw)
    t[23 + n], t[24 + n] = c & 0xFF, c >> 8
    Lfsr(63).whiten(t, 18)
    Lfsr(37).whiten(t, 0)
    keep = n + 10
    out = bytearray(t[15:15 + keep]) + bytes(i + 1 for i in range(keep, 24))
    return bytes(out[:24])


def decode(air):
    """Inverse of encode: 24-byte on-air data -> (raw bytes, crc_ok). The keystreams are data-independent."""
    air = bytes(air)
    keep = len(air)
    while keep and air[keep - 1] == keep:          # strip filler byte[i] = i+1
        keep -= 1
    n = keep - 10
    if n <= 0:
        return b'', False
    t = bytearray(n + 25)
    t[15:15 + keep] = air[:keep]
    Lfsr(37).whiten(t, 0)
    Lfsr(63).whiten(t, 18)
    raw = bytes(t[23:23 + n])
    c = crc16(raw)
    return raw, (t[23 + n] == c & 0xFF and t[24 + n] == c >> 8)


VECTORS = [  # (raw, on-air) published in moldqueen linux-core/mk4web/mouldking_crypt.py self-test
    ('6d7ba78080808092', '6db643cf7e8f471188665938d17aaa26495e131415161718'),
    ('617ba78080808080809e', '6db643cf7e8f471184665938d17aaa34674a55bf15161718'),
    ('617ba7b980808080809e', '6db643cf7e8f471184665901d17aaa34674a262815161718'),
]

if __name__ == '__main__':
    if sys.argv[1:] == ['--test']:
        bad = 0
        for raw, air in VECTORS:
            got = encode(raw).hex()
            ok = got == air
            bad += not ok
            print(('PASS' if ok else 'FAIL'), raw, got)
        sys.exit(1 if bad else 0)
    for raw in sys.argv[1:]:
        print(encode(raw).hex())
