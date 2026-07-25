"""Check if .reset-prompt triggers zle-line-pre-redraw (which calls _prompt_zle_append_footer)."""
import os, pty, select, time, glob

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

_logf=/tmp/rp_log.$$
_prompt_zle_append_footer() {
  emulate -L zsh
  echo "APPEND_FOOTER WIDGET=[$WIDGET]" >&2
  # Don't call original — just log
}

TRAPUSR1() {
  emulate -L zsh
  echo "TRAP_FIRED" >&2
  _prompt_rendering=1
  _prompt_precmd
  _prompt_rendering=0
  zle .reset-prompt 2>/dev/null
  echo "TRAP_DONE" >&2
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

text = out.decode('utf-8', errors='replace')
for line in text.split('\n'):
    if any(x in line for x in ['TRAP_', 'APPEND_']):
        clean = line.replace('\x1b', 'ESC')
        print(repr(clean.strip()[:120]))
os.close(fd); os.waitpid(pid, 0)
