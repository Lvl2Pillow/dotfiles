#!/usr/bin/env python3
"""Try cd to ~/.zsh (appears in error) then to chezmoi source."""
import os, pty, select, time

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            break
        try:
            chunk = os.read(fd, 8192)
            if not chunk:
                break
            out += chunk
        except OSError:
            break
    return out

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'
    os.environ['LINES'] = '24'
    os.environ['TERM_PROGRAM'] = ''
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.8)
read_all(fd, 0.5)
read_all(fd, 0.3)

# cd to ~/.zsh
print("=== cd ~/.zsh ===")
os.write(fd, b'cd ~/.zsh\n')
time.sleep(0.5)
out = read_all(fd, 0.3)
print(f"Output: {out[-400:]!r}")
if b'permission' in out.lower():
    print("*** PERMISSION DENIED! ***")

# That worked? Now cd to chezmoi source
print("=== cd ~/.local/share/chezmoi ===")
os.write(fd, b'cd "$(chezmoi source-path)"\n')
time.sleep(0.8)
out = read_all(fd, 0.5)
print(f"Output: {out[-500:]!r}")
if b'permission' in out.lower():
    print("*** PERMISSION DENIED! ***")

os.write(fd, b'exit\n')
time.sleep(0.2)
os.close(fd)
os.waitpid(pid, 0)
