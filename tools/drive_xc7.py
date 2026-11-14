"""Drive the XP Block XC-7 page (two joysticks A/B and C/D, sliders E and F) one action at a time via adb.
Phone: LG D722 landscape (rotation 90): logical (lx, ly) = (raw_y, 720 - raw_x), raw = portrait screenshot."""
import subprocess, time, datetime


def sh(*a):
    subprocess.run(['adb', 'shell', 'input', *map(str, a)], check=True)


def mark(label):
    print(datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3], label, flush=True)


def raw(px, py):
    return py, 720 - px


J1, J2 = raw(235, 410), raw(235, 785)      # joystick centres (A/B and C/D)
R = 100                                     # swipe radius in px
E0, E1 = raw(555, 375), raw(555, 550)       # slider E ends
F0, F1 = raw(555, 640), raw(555, 820)       # slider F ends


def swipe(c, dx, dy, ms=1200):
    sh('swipe', c[0], c[1], c[0] + dx, c[1] + dy, ms)


steps = [
    ('J1 screen-up', lambda: swipe(J1, 0, -R)), ('J1 screen-down', lambda: swipe(J1, 0, R)),
    ('J1 screen-left', lambda: swipe(J1, -R, 0)), ('J1 screen-right', lambda: swipe(J1, R, 0)),
    ('J2 screen-up', lambda: swipe(J2, 0, -R)), ('J2 screen-down', lambda: swipe(J2, 0, R)),
    ('J2 screen-left', lambda: swipe(J2, -R, 0)), ('J2 screen-right', lambda: swipe(J2, R, 0)),
    ('E to screen-left end', lambda: sh('swipe', *raw(555, 463), *E0, 1000)),
    ('E to screen-right end', lambda: sh('swipe', *raw(555, 463), *E1, 1000)),
    ('F to screen-left end', lambda: sh('swipe', *raw(555, 730), *F0, 1000)),
    ('F to screen-right end', lambda: sh('swipe', *raw(555, 730), *F1, 1000)),
]
for label, act in steps:
    mark(label)
    act()
    time.sleep(1.5)
mark('done')
