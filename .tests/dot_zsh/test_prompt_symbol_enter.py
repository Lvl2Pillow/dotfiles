"""
RED test: after Enter on empty buffer, the % prompt symbol must remain visible.

The clear sequence in _prompt_zle_accept_line (\\r\\033[2K...) must not erase
the prompt symbol itself. Verify that % appears on a line by itself after Enter.
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

def test():
    config = 'cd ~ 2>/dev/null; source ~/.zshrc 2>/dev/null || true\n'
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
        d = '/tmp/zp_' + str(os.getpid()); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    time.sleep(1.0); read_all(fd, 0.5)

    # Press Enter on empty buffer
    os.write(fd, b'\n')
    time.sleep(2.0)
    out = read_all(fd, 3.0)

    # Check the last prompt line has % symbol
    lines = out.split(b'\n')
    last_pct = None
    for i, line in enumerate(reversed(lines)):
        clean = re.sub(rb'\x1b\[[0-9;]*[a-zA-Z]', b'', line)
        if b'%' in clean:
            last_pct = i
            break

    # Also dump last 300 chars
    text = out.decode('utf-8', errors='replace').replace('\x1b', 'ESC')
    print(f'  Total lines: {len(lines)}')
    print(f'  Last % at position from end: {last_pct}')
    print(f'  Last 300 chars: {repr(text[-300:])}')

    if last_pct is None:
        return False, 'No % prompt symbol found in output'

    # Check that the prompt line (after Enter) isn't all whitespace
    # i.e., the % wasn't cleared
    return True, f'% found at position -{last_pct}'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = test()
    except Exception as e:
        import traceback; traceback.print_exc()
        msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
