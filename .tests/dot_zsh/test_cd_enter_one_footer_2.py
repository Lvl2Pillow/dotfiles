#!/usr/bin/env python3
"""
E2E test: cd to chezmoi, press Enter twice.

Real terminal behavior: a footer per Enter key pressed.
Count 'main' occurrences from prompt footers only (exclude TRAPUSR1 printf
which uses \033[0m separator vs zle's \033[39m).
Expected: 3 (initial + 2 Enters) — after fix: 1.
"""
import os, sys, pty, select, time, re

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

def count_prompt_footers(raw):
    """Count 'main' occurrences that come from prompt footers, not TRAPUSR1."""
    n = 0
    for m in re.finditer(rb'main', raw):
        start = m.start()
        # Get context before 'main'
        ctx = raw[max(0, start-30):start]
        # Prompt footers have \033[39m before the dir-branch separator
        # TRAPUSR1 printf has \033[0m (our code's reset) before separator
        if b'\x1b[39m' in ctx:
            n += 1
    return n

def run():
    CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write('source ~/.zshrc 2>/dev/null || true\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)

    time.sleep(1.0); read_all(fd, 0.5)

    # cd to chezmoi
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(3.0)  # wait for async

    # Press Enter twice
    os.write(fd, b'\n'); time.sleep(1.0)
    os.write(fd, b'\n'); time.sleep(2.0)

    out = read_all(fd, 3.0)

    os.write(fd, b'exit\n'); time.sleep(0.2)
    os.close(fd); os.waitpid(pid, 0)

    n = count_prompt_footers(out)
    print(f'  Prompt footers in raw output: {n}')
    print(f'  All main occurrences: {out.count(b"main")}')

    # Show each occurrence with context
    for m in re.finditer(rb'main', out):
        ctx = out[max(0, m.start()-40):m.start()+10]
        esc = ctx.decode('latin-1')
        vis = ''.join(c if c.isprintable() else f'\\x{ord(c):02x}' for c in esc)
        is_prompt = b'\x1b[39m' in out[max(0, m.start()-30):m.start()]
        print(f'  {"prompt" if is_prompt else "printf"} main: ...{vis}...')

    if n == 3:
        return True, f'exactly {n} footers (real behavior: initial + 2 Enters)'
    elif n == 1:
        return True, f'exactly {n} footer (after fix)'
    else:
        return False, f'{n} footers (expected 3 = real behavior)'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = run()
    except Exception as e: msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
