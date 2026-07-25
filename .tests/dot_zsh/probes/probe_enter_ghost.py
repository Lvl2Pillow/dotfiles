#!/usr/bin/env python3
"""Capture ALL terminal output after Enter, looking for old footer leak."""
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

# Ok, drain initial prompt output fully
time.sleep(0.3); raw_init = read_all(fd, 0.5)

# Type a simple command with NO ghost text
os.write(fd, b'echo hello world\n')
time.sleep(0.8)
raw = read_all(fd, 0.3)

text = raw.decode('utf-8', errors='replace')
print("=== Raw after Enter ===")
for i, l in enumerate(text.split('\n')[:15]):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:140]}")

# Now type something that has ghost text suggestion
os.write(fd, b'echo h')
time.sleep(1.5)
read_all(fd, 0.3)

# Now press Enter (NOT Ctrl+F)
os.write(fd, b'\n')
time.sleep(0.8)
raw2 = read_all(fd, 0.5)

text2 = raw2.decode('utf-8', errors='replace')
print("\n=== After Enter with ghost text ===")
for i, l in enumerate(text2.split('\n')[:15]):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:140]}")

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
