#!/usr/bin/env python3
"""Prove buffer contamination: check if buffer contains \n after accept."""
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

# Print buffer length and raw content using zle -U trick
# Send escape sequence to dump buffer state
os.write(fd,b'echo "${#BUFFER} ${BUFFER}"\n')
time.sleep(0.5)
out = read_all(fd,0.5)
text = out.decode('utf-8',errors='replace')
clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',text)
clean = re.sub(r'\x1b\][^\x07]*\x07','',clean)
clean = clean.replace('\r','')
print("Output after buffer dump:")
for line in clean.split('\n'):
    line = line.strip()
    if line:
        print(f"  {line!r}")

os.write(fd,b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid,0)
