#!/usr/bin/env python3
"""Check if colors leak into buffer after accept."""
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

# Capture raw output after accept WITHOUT Ctrl+L (to see live state)
# Just press enter and look at the output
os.write(fd,b'\n')  # execute the buffer
time.sleep(0.5)
out = read_all(fd,0.3)
text = out.decode('utf-8',errors='replace')

# Look for color codes (38;5;N or fg=) in the output
# After executing 'echo hello world', we should see just 'hello world'
# without any color codes
colors = re.findall(r'\x1b\[[0-9;]*m', text)
print(f"Color codes found: {len(colors)}")
for c in colors:
    print(f"  {c!r}")

# Show clean output
clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',text)
clean = re.sub(r'\x1b\][^\x07]*\x07','',clean)
clean = clean.replace('\r','')
print(f"\nClean output:")
for l in clean.split('\n'):
    if l.strip():
        print(f"  {l.strip()!r}")

os.write(fd,b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid,0)
