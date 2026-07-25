"""
RED test: after Enter on empty buffer, old footer must be cleared.

Uses terminal-aware logic: in each \n segment, if a \033[2K (erase entire line)
appears AFTER the last footer text occurrence, the footer was cleared on the
real terminal and should NOT be counted as visible.

After ONE Enter on empty buffer, there should be exactly 1 visible footer
(the new prompt's footer).
"""
import os, sys, pty, select, time, re

def read_all(fd, timeout=0.8):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

def strip_ansi(b):
    return re.sub(rb'\x1b\[[0-9;]*[a-zA-Z]', b'', b)

def count_visible_footers(out):
    """Count footer lines as they appear on a real terminal.
    
    Split by \n. For each segment, if the LAST occurrence of the footer
    pattern is followed by \033[2K (erase entire line), the footer was
    cleared and should NOT be counted.
    """
    lines = out.split(b'\n')
    visible = 0
    for line in lines:
        clean = strip_ansi(line)
        # Look for ~path branch pattern (footer at column 1)
        if not re.search(rb'(~/\S+ \S+)', clean):
            continue
        # Find the raw position of the LAST 'main' occurrence
        last_main = line.rfind(b'main')
        if last_main < 0:
            continue
        # Check if there's a \033[2K AFTER 'main' (means line was erased)
        tail = line[last_main + 4:]
        if b'[2K' in tail or b'\x1b[J' in tail:
            continue
        visible += 1
    return visible

def count_paste_footers(out):
    """Count footers in paste (naive \n split + ANSI strip)."""
    t = out.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    ls = t.split(b'\n')
    return sum(1 for l in ls if b'chezmoi' in strip_ansi(l) and b'main' in strip_ansi(l))

def test():
    config = 'source ~/.zshrc 2>/dev/null || source ~/.local/share/chezmoi/dot_zsh/05_prompt.zsh 2>/dev/null\n'
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
        d = '/tmp/zsh_probe_' + str(os.getpid())
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)
    time.sleep(1.0); read_all(fd, 0.5)
    CHEZMOI = os.path.expanduser('~/.local/share/chezmoi')
    os.write(fd, f'cd {CHEZMOI}\n'.encode())
    time.sleep(3.0)
    os.write(fd, b'\n')  # Enter on empty buffer
    time.sleep(2.0)
    out = read_all(fd, 3.0)
    os.write(fd, b'exit\n'); time.sleep(0.2)
    os.close(fd); os.waitpid(pid, 0)

    term_footers = count_visible_footers(out)
    paste_footers = count_paste_footers(out)
    
    print(f'  Visible footers (terminal-aware): {term_footers}')
    print(f'  Visible footers (paste-naive):    {paste_footers}')
    
    if term_footers > 1:
        return False, f'{term_footers} visible footers — old footer NOT cleared by accept-line'
    if term_footers == 0:
        return False, 'No footer found at all'
    return True, f'OK: {term_footers} footer(s) visible'

if __name__ == '__main__':
    ok, msg = False, 'exception'
    try: ok, msg = test()
    except Exception as e:
        import traceback; traceback.print_exc()
        msg = str(e)
    print(f'  {"PASS" if ok else "FAIL"}: {msg}')
    sys.exit(0 if ok else 1)
