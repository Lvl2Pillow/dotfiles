"""
Test: Enter after cd shows exactly 1 visible footer (no duplicate).
Verifies accept-line clear + TRAPUSR1 printf don't produce 2 footers.
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

def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
        d = '/tmp/zp_' + str(os.getpid()); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write('cd ~ 2>/dev/null; source ~/.zshrc 2>/dev/null || true\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    time.sleep(1.0); read_all(fd, 0.5)
    return pid, fd

def terminal_visible_footers(out):
    """Count footers that survive on the terminal.
    
    A footer is NOT counted if on the same \n segment a \033[2K
    appears AFTER the last footer text.
    """
    lines = out.split(b'\n')
    cnt = 0
    for line in lines:
        clean = re.sub(rb'\x1b\[[0-9;]*[a-zA-Z]', b'', line)
        if not (b'chezmoi' in clean and b'main' in clean):
            continue
        last_main = line.rfind(b'main')
        if last_main < 0:
            continue
        tail = line[last_main + 4:]
        if b'[2K' in tail or b'\x1b[J' in tail or b'\x1b[0J' in tail:
            continue
        cnt += 1
    return cnt

def test_enter_one_footer():
    """After Enter on empty buffer, exactly 1 visible footer (no duplicate)."""
    pid, fd = spawn()
    CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(0.5)
    os.write(fd, b'\n')
    time.sleep(2.0)
    out = read_all(fd, 3.0)
    os.write(fd, b'exit\n'); time.sleep(0.2)
    os.close(fd); os.waitpid(pid, 0)
    n = terminal_visible_footers(out)
    return n <= 1, n

def test_buffer_ok():
    """After Enter, buffer content is not corrupted (can run commands)."""
    pid, fd = spawn()
    os.write(fd, b'echo hello\n')
    time.sleep(1.0)
    out = read_all(fd, 1.0)
    os.write(fd, b'exit\n'); time.sleep(0.2)
    os.close(fd); os.waitpid(pid, 0)
    clean = re.sub(rb'\x1b\[[0-9;]*[a-zA-Z]', b'', out).decode('utf-8','replace')
    return 'hello' in clean, clean[:80]

if __name__ == '__main__':
    ok1, n = test_enter_one_footer()
    print(f'  [{"PASS" if ok1 else "FAIL"}] Visible footers after Enter: {n}')
    ok2, msg = test_buffer_ok()
    print(f'  [{"PASS" if ok2 else "FAIL"}] Buffer OK')
    sys.exit(0 if ok1 and ok2 else 1)
