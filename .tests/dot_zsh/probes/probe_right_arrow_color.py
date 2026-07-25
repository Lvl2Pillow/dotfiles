#!/usr/bin/env python3
"""Test: RIGHT ARROW (not Ctrl+F) to accept suggestion — check for color leak."""
import os, sys, pty, select, time, re

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

os.write(fd, b'echo hello world\n')
time.sleep(0.6); read_all(fd, 0.3)

os.write(fd, b'echo h')
time.sleep(1.5); read_all(fd, 0.3)

# Accept with RIGHT ARROW
os.write(fd, b'\x1b[C')
time.sleep(0.5)
raw = read_all(fd, 0.3)

# Redraw to capture final state
os.write(fd, b'\x0c')
time.sleep(0.5)
raw2 = read_all(fd, 0.5)

text = raw2.decode('utf-8', errors='replace')
lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

print("=== After RIGHT ARROW + Ctrl+L ===")
for i, l in enumerate(lines[:10]):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:140]}")

# Check for color codes in buffer area
for l in lines:
    if '%' in l:
        clean = l.replace('\x1b', 'ESC')
        reset_pos = clean.rfind('ESC[0m')
        if reset_pos >= 0:
            buf = clean[reset_pos:]
        else:
            buf = clean
        colors = re.findall(r'ESC\[[0-9;]*m', buf)
        disallowed = [c for c in colors if c not in ('ESC[0m','ESC[K','ESC[39m','ESC[27m','ESC[24m')]
        if disallowed:
            print(f"\n[FAIL] Color codes: {disallowed}")
        else:
            print(f"\n[PASS] Clean buffer")
        break

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
