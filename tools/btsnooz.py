"""Turn the BTSNOOP_LOG_SUMMARY block of `adb shell dumpsys bluetooth_manager` into a btsnoop file.
Android keeps a compressed ring buffer of recent HCI packets there even when the full snoop log is off.
Format (AOSP btsnooz): base64 -> version (1 byte), last timestamp ms (8 bytes LE), zlib data;
records: v1 '<HIb' (length, delta ms, type), v2 '<HHIb' (length, original length, delta ms, type),
followed by length-1 bytes. Usage: btsnooz.py dumpsys.txt out.log
"""
import base64, re, struct, sys, zlib

TYPES = {  # snooz type -> (H4 indicator, direction flags: 1 = received)
    0x10: (4, 1), 0x11: (2, 1), 0x12: (3, 1), 0x17: (5, 1),
    0x20: (1, 0), 0x21: (2, 0), 0x22: (3, 0), 0x27: (5, 0),
}
EPOCH = 0x00dcddb30f2f8000

txt = open(sys.argv[1], encoding='utf-8', errors='replace').read()
m = re.search(r'--- BEGIN:BTSNOOP_LOG_SUMMARY[^\n]*\n(.*?)--- END:BTSNOOP_LOG_SUMMARY', txt, re.S)
if not m:
    sys.exit('no BTSNOOP_LOG_SUMMARY block')
raw = base64.b64decode(re.sub(r'\s+', '', m.group(1)))
ver, last_ms = raw[0], struct.unpack('<q', raw[1:9])[0]
data = zlib.decompress(raw[9:])
hdr, hlen = ('<HHIb', 9) if ver == 2 else ('<HIb', 7)

recs, off = [], 0
while off + hlen <= len(data):
    if ver == 2:
        length, orig, delta, typ = struct.unpack_from(hdr, data, off)
    else:
        length, delta, typ = struct.unpack_from(hdr, data, off)
        orig = length
    off += hlen
    recs.append((orig, delta, typ & 0xff, data[off:off + length - 1]))
    off += length - 1

unit = 1 if last_ms > 10**14 else 1000          # some builds store microseconds despite the name
t = last_ms - sum(r[1] for r in recs)        # deltas are relative to the previous record
out = open(sys.argv[2], 'wb')
out.write(b'btsnoop\0' + struct.pack('>II', 1, 1002))
for orig, delta, typ, payload in recs:
    t += delta
    ind, rx = TYPES.get(typ, (0, 0))
    pkt = bytes([ind]) + payload
    out.write(struct.pack('>IIIIq', orig + 1, len(pkt), rx, 0, t * unit + EPOCH))
    out.write(pkt)
print(f'version {ver}, {len(recs)} records -> {sys.argv[2]}')
