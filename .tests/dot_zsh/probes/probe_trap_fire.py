"""Check if TRAPUSR1 fires when starting from HOME and cd to chezmoi."""
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
cd ~ 2>/dev/null
source ~/.zshrc 2>/dev/null || true

_logf=/tmp/tr_log.$$
TRAPUSR1() {
  emulate -L zsh
  echo "TRAP_FIRED WIDGET=[$WIDGET]" >&2
  _prompt_rendering=1
  _prompt_precmd
  _prompt_rendering=0
  _prompt_zle_append_footer
  zle .reset-prompt 2>/dev/null
  echo "TRAP_DONE" >&2
}
'''

for f in glob.glob('/tmp/tr_log.*'): os.unlink(f)

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

# Check for TRAP markers in output
text = out.decode('utf-8', errors='replace')
for line in text.split('\n'):
    if 'TRAP' in line:
        clean = line.replace('\x1b', 'ESC')
        print(repr(clean.strip()[:120]))

# Check last footer color
if 'TRAP_DONE' in text:
    print('TRAPUSR1 completed fully (TRAP_DONE seen)')
if 'TRAP_FIRED' in text:
    print('TRAPUSR1 fired but may not have completed')
if 'TRAP_FIRED' not in text and 'TRAP_DONE' not in text:
    print('TRAPUSR1 NEVER fired!')
    # Show last part of output
    print('--- Last output ---')
    print(text[-500:])

os.close(fd); os.waitpid(pid, 0)
