"""Replay the Power Box app's captured broadcast frames from the mk_broadcaster ESP32.
Usage: pb_replay.py COM7
Advertising data = flags 02 01 1a + manufacturer AD 1b ff + 26 captured bytes (byte 11 = control byte)."""
import sys, time, datetime
import serial

PREFIX = '02011a1bff'
FRAMES = {  # control byte -> 26 captured bytes (Samsung + Power Box "M Serial", driving the real car)
    'ba': 'ddb2da6c9f017a34d3c358ba980824cb3bfc71a3f4556847d8ff',
    'b2': 'ddb2da6c9f017a34d3c358b2980824cb3bfc71a3f455684bdc18',
    'b8': 'ddb2da6c9f017a34d3c358b8980824cb3bfc71a3f455684590d7',
    'b4': 'ddb2da6c9f017a34d3c358b4980824cb3bfc71a3f455684e9f52',
    'b3': 'ddb2da6c9f017a34d3c358b3980824cb3bfc71a3f455684af80c',
    'b9': 'ddb2da6c9f017a34d3c358b9980824cb3bfc71a3f4556844b4c3',
    'b5': 'ddb2da6c9f017a34d3c358b5980824cb3bfc71a3f455684fbb46',
}
s = serial.Serial(sys.argv[1], 115200, timeout=0.2)
time.sleep(2.5)
s.reset_input_buffer()


def hold(label, key, secs):
    print(f'{datetime.datetime.now():%H:%M:%S}  >>> {label:<26} byte11={key}', flush=True)
    end = time.time() + secs
    while time.time() < end:
        s.write(f'R {PREFIX}{FRAMES[key]}\n'.encode())
        time.sleep(0.15)


try:
    hold('IDLE (bind?)', 'ba', 4)
    for k in ['b2', 'b8', 'b4', 'b3', 'b9', 'b5']:
        hold(f'command {k}', k, 2)
        hold('idle', 'ba', 1.5)
finally:
    s.write(b'S\n')
    print('stopped', flush=True)
