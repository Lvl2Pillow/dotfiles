import os, pty, select, time, re

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

# Use EXACT same approach as spawn_real: .zshenv overrides ZDOTDIR to $HOME
config = 'source ~/.zshrc 2>/dev/null || true'
pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
    d = f'/tmp/zsh_probe_spawn_{os.getpid()}'; os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
    with open(os.path.join(d, '.zshenv'), 'w') as f: f.write('export ZDOTDIR="$HOME"\n')
    os.environ['ZDOTDIR'] = d
    os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

time.sleep(1.0); read_all(fd, 0.5)
os.write(fd, b'\n'); time.sleep(0.8)
raw = read_all(fd, 0.8)

def strip_ansi(s):
    s = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', s)
    s = re.sub(r'\x1b\][^\x07]*\x07', '', s)
    s = re.sub(r'\x1b[%#()]', '', s)
    s = re.sub(r'\x08', '', s)
    return s

text = raw.decode('utf-8', errors='replace')
stripped = strip_ansi(text)
lines = stripped.replace('\r\n', '\n').split('\n')
count = 0
for i, l in enumerate(lines):
    trimmed = l.strip()
    is_footer = (trimmed.startswith('/') or trimmed.startswith('~')) and ' ' in trimmed
    safe = repr(l[:120])
    print(f'  [{i}] {safe} {"FOOTER" if is_footer else ""}')
    if is_footer: count += 1
print(f'Footer count: {count}')
os.close(fd); os.waitpid(pid, 0)
