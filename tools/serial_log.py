"""Log a serial port to stdout and a file with PC timestamps. Ctrl+C to stop.
Usage: serial_log.py COM75 out.txt [baud]   (needs pyserial; PlatformIO's penv python has it)"""
import sys, time, datetime
import serial

port, out = sys.argv[1], sys.argv[2]
baud = int(sys.argv[3]) if len(sys.argv) > 3 else 115200
with open(out, 'a', encoding='utf-8', buffering=1) as f:
    while True:
        try:
            with serial.Serial(port, baud, timeout=0.5) as s:
                print(f'# opened {port}', flush=True)
                buf = b''
                while True:
                    buf += s.read(256)
                    while b'\n' in buf:
                        line, buf = buf.split(b'\n', 1)
                        txt = f'{datetime.datetime.now():%H:%M:%S.%f}'[:-3] + ' ' + line.decode('utf-8', 'replace').rstrip()
                        print(txt, flush=True)
                        f.write(txt + '\n')
        except serial.SerialException as e:      # port vanishes while the board resets/reflashes
            print(f'# {e}; retrying', flush=True)
            time.sleep(1)
