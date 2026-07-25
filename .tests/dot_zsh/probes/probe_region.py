#!/usr/bin/env python3
"""Dump region_highlight positions after accept."""
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

# Dump region_highlight via widget
os.write(fd,b'echo "BUFFER=$BUFFER"\n')
time.sleep(0.3); read_all(fd,0.2)

# Also check what _prompt and _prompt_dir_len are
os.write(fd,b'echo "_prompt=$_prompt  _prompt_dir_len=$_prompt_dir_len"\n')
time.sleep(0.3); out = read_all(fd,0.3)

text = out.decode('utf-8',errors='replace')
clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',text)
clean = re.sub(r'\x1b\][^\x07]*\x07','',clean)
clean = clean.replace('\r','')
print("Debug output:")
for l in clean.split('\n'):
    l = l.strip()
    if l and not l.startswith('echo'):
        print(f"  {l}")

# Now let's look at the region_highlight by examining what's drawn on screen
# Strip escape sequences and look at the raw bytes
os.write(fd,b'zmodload zsh/zle 2>/dev/null; print -r -- "${region_highlight[@]}"\n')
time.sleep(0.3); out2 = read_all(fd,0.3)
text2 = out2.decode('utf-8',errors='replace')
clean2 = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',text2)
clean2 = re.sub(r'\x1b\][^\x07]*\x07','',clean2)
clean2 = clean2.replace('\r','')
print("\nRegion highlight:")
for l in clean2.split('\n'):
    l = l.strip()
    if l and l[0].isdigit():
        print(f"  {l}")

os.write(fd,b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid,0)
