#!/usr/bin/env python3
"""Check for footer leak after Ctrl+C."""
import os, pty, select, time, re

def read_all(fd, t=0.5):
    out=b''
    while True:
        r,_,_=select.select([fd],[],[],t)
        if not r: break
        try:
            c=os.read(fd,8192)
            if not c: break
            out+=c
        except: break
    return out

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM']='xterm-256color'; os.environ['COLUMNS']='80'; os.environ['LINES']='24'
    os.execvpe('zsh',['zsh','-i'],os.environ); os._exit(1)

time.sleep(0.8); read_all(fd, 0.5)

# Capture initial prompt output
os.write(fd, b'\x03')  # Ctrl+C on empty buffer
time.sleep(0.5)
raw = read_all(fd, 0.5)
text = raw.decode('utf-8', errors='replace')
lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
print("=== Ctrl+C on empty ===")
for i, l in enumerate(lines[:5]):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:120]}")

# Now type a command and press Ctrl+C
os.write(fd, b'echo hello')
time.sleep(0.3)
read_all(fd, 0.2)
os.write(fd, b'\x03')
time.sleep(0.5)
raw2 = read_all(fd, 0.5)
text2 = raw2.decode('utf-8', errors='replace')
lines2 = text2.replace('\r\n', '\n').replace('\r', '\n').split('\n')
print("\n=== Ctrl+C on 'echo hello' ===")
for i, l in enumerate(lines2[:8]):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:120]}")

# Check: how many footers visible?
all_lines = text2.split('\n')
footer_count = 0
for l in all_lines:
    if re.search(r'~\S+', l) and 'echo' not in l and 'file://' not in l:
        footer_count += 1
print(f"\nFooter lines found: {footer_count}")

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
