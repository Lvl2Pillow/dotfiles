#!/usr/bin/env python3
"""Check prompt line colors after accept, before Enter."""
import os, pty, select, time, re

def read_all(fd, t=0.5):
    out = b''
    while True:
        r,_,_ = select.select([fd],[],[],t)
        if not r: break
        try:
            c = os.read(fd,8192)
            if not c: break
            out += c
        except: break
    return out

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM']='xterm-256color'; os.environ['COLUMNS']='80'; os.environ['LINES']='24'
    os.execvpe('zsh',['zsh','-i'],os.environ); os._exit(1)

time.sleep(0.8); read_all(fd,0.5)
os.write(fd,b'echo hello world\n'); time.sleep(0.5); read_all(fd,0.3)
os.write(fd,b'echo h'); time.sleep(1.5); read_all(fd,0.3)

# Accept with Ctrl+F
os.write(fd,b'\x06'); time.sleep(0.5); read_all(fd,0.3)

# DON'T press Enter. Instead, capture the current display state
# by sending Ctrl+L and capturing ALL escape sequences
os.write(fd,b'\x0c')
time.sleep(0.3)
out = read_all(fd,0.3)
text = out.decode('utf-8',errors='replace')

# Print escape sequences
print("Raw output after Ctrl+L (annotated):")
# Split by \x1b
parts = text.split('\x1b')
for i, p in enumerate(parts):
    if p:
        seq = p[:20]  # first 20 chars
        rest = p[20:] if len(p) > 20 else ''
        # Check if it's a CSI sequence
        if seq[0] == '[':
            print(f"  ESC[{seq}")
        else:
            print(f"  literal {seq[:30]!r}")

# Look for color codes before 'echo hello world' text
# The prompt line should have: prompt + buffer + clear-to-EOL
# Buffer should be plain text without color codes
idx = text.find('echo hello world')
if idx >= 0:
    before = text[max(0,idx-100):idx+20]
    print(f"\nContext around 'echo hello world': {before!r}")
    if '\x1b[38;5' in before:
        print("[RED] Color code found BEFORE buffer text - leaking!")
    else:
        print("[GREEN] No color codes before buffer text")

os.write(fd,b'\n'); time.sleep(0.2); read_all(fd,0.1)
os.write(fd,b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid,0)
