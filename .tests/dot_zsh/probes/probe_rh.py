#!/usr/bin/env python3
"""Debug: after accept, use zle widget call to print region_highlight."""
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

# NOW: define a widget that prints region_highlight, BUFFER length, POSTDISPLAY length, _prompt length
# Use bindkey to a rare key and inject via zle -U
script = '''
_prompt_debug() {
  local output="BUFFER=$#BUFFER POSTDISPLAY=$#POSTDISPLAY _prompt=$#_prompt _prompt_dir_len=$_prompt_dir_len"
  output+=" RH: ${region_highlight[*]}"
  print -r -- "$output" >/dev/tty
  zle -M "$output"
}
zle -N _prompt_debug
bindkey '^[^[^[' _prompt_debug
'''
for ch in script:
    os.write(fd, ch.encode())
    time.sleep(0.001)

time.sleep(0.2)
read_all(fd, 0.3)

# Trigger the debug widget with ESC ESC ESC
os.write(fd, b'\x1b\x1b\x1b')
time.sleep(0.3)
out = read_all(fd, 0.3)

text = out.decode('utf-8',errors='replace')
clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]','',text)
clean = re.sub(r'\x1b\][^\x07]*\x07','',clean)
clean = clean.replace('\r','').replace('\x1b','')
print("Debug output:")
for l in clean.split('\n'):
    l = l.strip()
    if l and ('BUFFER=' in l or 'RH:' in l or 'BUFFER' in l):
        print(f"  {l}")

os.write(fd,b'\n'); time.sleep(0.2); read_all(fd,0.1)
os.write(fd,b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid,0)
