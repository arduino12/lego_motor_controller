"""Drive the XC-6 remote page with adb input, one isolated action at a time, printing UTC timestamps.
Phone is LG D722 in landscape (rotation 90): logical (lx, ly) = (raw_y, 720 - raw_x)."""
import subprocess, time, datetime, sys

def sh(*a):
    subprocess.run(['adb', 'shell', 'input', *map(str, a)], check=True)

def mark(label):
    print(datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S.%f')[:-3], label, flush=True)

def raw(px, py):
    return py, 720 - px

PLUS, MINUS, STOP = raw(460, 120), raw(128, 120), raw(293, 120)
SL_C, SL_TOP, SL_BOT = raw(293, 1075), raw(535, 1075), raw(52, 1075)
SOUNDS = [raw(172, y) for y in (292, 413, 535, 658, 782, 903)]
GAP = 1.6

steps = sys.argv[1] if len(sys.argv) > 1 else 'buttons'
if steps == 'buttons':
    for i in range(3):
        mark(f'tap + #{i+1}'); sh('tap', *PLUS); time.sleep(GAP)
    mark('tap STOP'); sh('tap', *STOP); time.sleep(GAP)
    for i in range(3):
        mark(f'tap - #{i+1}'); sh('tap', *MINUS); time.sleep(GAP)
    mark('tap STOP'); sh('tap', *STOP); time.sleep(GAP)
elif steps == 'slider':
    mark('swipe slider center->top 1200ms'); sh('swipe', *SL_C, *SL_TOP, 1200); time.sleep(GAP)
    mark('swipe slider center->bottom 1200ms'); sh('swipe', *SL_C, *SL_BOT, 1200); time.sleep(GAP)
    mark('swipe slider center->half-up 800ms'); sh('swipe', *SL_C, *raw(414, 1075), 800); time.sleep(GAP)
elif steps == 'sounds':
    for i, p in enumerate(SOUNDS):
        mark(f'tap sound/fx button {i+1}'); sh('tap', *p); time.sleep(GAP)
mark('done')
