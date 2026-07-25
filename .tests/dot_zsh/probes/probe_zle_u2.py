"""Test zle -U with longer wait for processing."""
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

TRAPUSR1() {
  emulate -L zsh
  _prompt_rendering=1
  _prompt_precmd
  _prompt_rendering=0
  # Inject space+backspace — will be processed when ZLE returns to main loop
  zle -U " " 2>/dev/null
  zle -U $'\x08' 2>/dev/null
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
# Wait EVEN LONGER for injected characters to be processed
time.sleep(5.0)
out = read_all(fd, 5.0)

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

print('Branch:', 'RED (88)' if found_88 else 'GREEN (34)')

# Also check if the space character appeared in buffer
text = out.decode('utf-8', errors='replace')
if 'cd ' in text:
    idx = text.rfind('cd ')
    after = text[idx+3:idx+5]
    print(f'After cd command in output: {repr(after)}')
os.close(fd); os.waitpid(pid, 0)
