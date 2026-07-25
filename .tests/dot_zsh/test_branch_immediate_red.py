"""
RED test: after cd to chezmoi + async, branch should be red (88) immediately.
Requires printf in TRAPUSR1 for immediate terminal update.
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

CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')

def _branch_colors_in_output(out):
    """Return all unique branch color codes found (last of 2+ per \r segment + raw scan)."""
    colors = set()
    segments = out.split(b'\r')
    for seg in segments:
        found = re.findall(rb'38;5;(\d+)', seg)
        if len(found) >= 2:
            colors.add(found[-1].decode())
    # Also scan raw output for ESC[38;5;88 (from printf in TRAPUSR1)
    if b'38;5;88' in out:
        colors.add('88')
    return colors

def spawn_from_home():
    config = 'cd ~ 2>/dev/null\nsource ~/.zshrc 2>/dev/null || true\n'
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    time.sleep(1.0); read_all(fd, 0.5)
    return pid, fd

def test_branch_immediately_red_after_async():
    """After cd + async, branch should be red (88) without any keystroke."""
    pid, fd = spawn_from_home()
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(3.0)  # wait for async to complete
    out = read_all(fd, 5.0)  # capture all output including TRAPUSR1 printf

    os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)

    colors = _branch_colors_in_output(out)

    text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
    print(f'  Branch colors found: {colors}')
    print(f'  Last 500 chars: {repr(text[-500:])}')

    if '88' in colors:
        return True, f'red (88) found in output'
    return False, f'no dark red (88) found in output, got {colors}'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = test_branch_immediately_red_after_async()
    except Exception as e: msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
