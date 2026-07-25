"""Probe: check if POSTDISPLAY assignment aborts TRAPUSR1."""
import os, pty, select, time

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

config = r'''
source ~/.zshrc 2>/dev/null || true

TRAPUSR1() {
  emulate -L zsh
  echo "FIRED" >&2
  { POSTDISPLAY="test_ok" } 2>/dev/null
  echo "AFTER" >&2
  zle .reset-prompt 2>/dev/null
  echo "RESET_DONE" >&2
}
'''

CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')
pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.0); read_all(fd, 0.5)
os.write(fd, f'cd {CHEZMOI}\n'.encode())
time.sleep(2.0)
raw = read_all(fd, 3.0)
# Print all output (decode, clean)
text = raw.decode('utf-8', errors='replace')
# Find all lines containing our markers
for line in text.split('\n'):
    if any(x in line for x in ['FIRED', 'AFTER', 'RESET_DONE', 'read-only']):
        clean = line.replace('\x1b', 'ESC')
        print(repr(clean.strip()[:100]))
if 'AFTER' not in text:
    print("AFTER never found — { POSTDISPLAY= } 2>/dev/null ABORTS the handler!")
    # Print last 500 chars of output
    print("--- Last 500 chars ---")
    print(text[-500:])
os.close(fd); os.waitpid(pid, 0)
