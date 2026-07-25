"""Test fix: remove _prompt_zle_append_footer from TRAPUSR1, just .reset-prompt."""
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
cd ~ 2>/dev/null
source ~/.zshrc 2>/dev/null || true

# Patch TRAPUSR1 to NOT call _prompt_zle_append_footer
TRAPUSR1() {
  emulate -L zsh
  _prompt_rendering=1
  _prompt_precmd
  _prompt_rendering=0
  # Removed: _prompt_zle_append_footer (silently fails in signal handler)
  zle .reset-prompt 2>/dev/null
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
time.sleep(3.0)
out = read_all(fd, 5.0)

# Check last footer segment color
import re
segments = out.split(b'\r')
found_88 = False
for seg in reversed(segments):
    colors = re.findall(rb'38;5;(\d+)', seg)
    if len(colors) >= 2:
        bc = colors[-1].decode()
        if bc == '88':
            found_88 = True
            break

text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
print('Branch after async:', 'RED (88)' if found_88 else 'GREEN (34)')

# Now simulate user typing a character (triggers zle-line-pre-redraw)
os.write(fd, b' ')
time.sleep(0.5)
out2 = read_all(fd, 0.5)
segments2 = out2.split(b'\r')
found_88_after_key = False
for seg in reversed(segments2):
    colors = re.findall(rb'38;5;(\d+)', seg)
    if len(colors) >= 2:
        bc = colors[-1].decode()
        if bc == '88':
            found_88_after_key = True
            break

print('Branch after keypress:', 'RED (88)' if found_88_after_key else 'GREEN (34)')
os.close(fd); os.waitpid(pid, 0)
