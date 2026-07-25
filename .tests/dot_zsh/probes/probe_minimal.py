"""Minimal probe: does zsh even start?"""
import os, pty, select, time

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

# Minimal config - no patching
config = 'echo HELLO_PROBE >&2\n'

d = f'/tmp/zsh_probe_{os.getpid()}'
os.makedirs(d, exist_ok=True)
with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config)
with open(os.path.join(d, '.zshenv'), 'w') as f: f.write('export ZDOTDIR="$HOME"\n')

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(1.0)
raw = read_all(fd, 1.0)
print(f"PID={pid}")
print(f"Output ({len(raw)} bytes):")
print(raw.decode('utf-8', errors='replace')[:500])
os.close(fd); os.waitpid(pid, 0)
