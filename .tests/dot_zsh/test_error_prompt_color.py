"""
RED test: after command fails (non-zero exit), next prompt % symbol should be red.

Current behavior: % stays white regardless of exit status.
"""
import os, sys, pty, select, time

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TEST_DIR, '.venv', 'lib',
    f'python{sys.version_info.major}.{sys.version_info.minor}', 'site-packages'))

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try:
            c = os.read(fd, 8192)
            if not c: break
            out += c
        except: break
    return out

def spawn():
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '24'
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)
    time.sleep(0.8)
    read_all(fd, 0.5)
    return pid, fd

def test_failed_command_red_prompt():
    """After `false`, the next prompt % should be red (ANSI 196)."""
    pid, fd = spawn()

    # Run a failing command
    os.write(fd, b'false\n')
    time.sleep(0.5)
    raw = read_all(fd, 0.5)

    # The new prompt should have a red % symbol
    text = raw.decode('utf-8', errors='replace').replace('\r', '\n')

    # Look for the prompt pattern: a line ending with "% " (the new prompt)
    lines = text.split('\n')
    print("=== Output after false ===")
    for i, l in enumerate(lines[:15]):
        clean = l.replace('\x1b', 'ESC')
        print(f"{i:2d}: {repr(clean)[:160]}")

    # Check if any prompt symbol has red coloring (ESC[38;5;196m or ESC[91m before %)
    found_red_prompt = False
    for l in lines:
        if 'ESC[38;5;196m%' in l or 'ESC[91m%' in l or 'ESC[1m%' in l:
            found_red_prompt = True
            break

    # Alternative: look for the sequence: % with a 196 color somewhere in the line
    # The prompt is: BOLD + RED + % + f + space + b
    # In terminal output: ESC[1mESC[38;5;196m%ESC[39m ESC[0m
    for l in lines:
        clean = l.replace('\x1b', 'ESC')
        if '196' in clean and '%' in clean:
            found_red_prompt = True
            break

    os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)

    if found_red_prompt:
        print("[PASS] Red prompt symbol found after failed command")
        return True
    else:
        print("[FAIL] Prompt symbol is not red after `false`")
        return False

def test_successful_command_white_prompt():
    """After `true`, the prompt % should be white (no red coloring)."""
    pid, fd = spawn()

    # Run a successful command
    os.write(fd, b'true\n')
    time.sleep(0.5)
    raw = read_all(fd, 0.5)

    text = raw.decode('utf-8', errors='replace').replace('\r', '\n')
    lines = text.split('\n')

    print("=== Output after true ===")
    for i, l in enumerate(lines[:15]):
        clean = l.replace('\x1b', 'ESC')
        print(f"{i:2d}: {repr(clean)[:160]}")

    # Check there's NO red coloring on the prompt symbol
    has_red = False
    for l in lines:
        clean = l.replace('\x1b', 'ESC')
        if '196' in clean and '%' in clean:
            has_red = True
            break

    os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)

    if has_red:
        print("[FAIL] Prompt symbol is unexpectedly red after successful command")
        return False
    else:
        print("[PASS] Prompt symbol is white after successful command")
        return True

if __name__ == '__main__':
    tests = [
        ('failed command → red %', test_failed_command_red_prompt),
        ('successful command → white %', test_successful_command_white_prompt),
    ]
    pass_count = 0
    fail_count = 0
    for name, fn in tests:
        ok = False
        try: ok = fn()
        except Exception as e: print(f'  EXCEPTION: {e}')
        if ok:
            pass_count += 1; print(f'  PASS: {name}')
        else:
            fail_count += 1; print(f'  FAIL: {name}')
    print(f'\n{pass_count}/{pass_count + fail_count} passed')
    sys.exit(0 if fail_count == 0 else 1)
