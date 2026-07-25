#!/usr/bin/env python3
"""
RED test: after accepting an autosuggestion (Right Arrow / Ctrl+F), the buffer
text must NOT contain color codes — the footer's purple/bold must not leak into
the command text.
"""
import os, sys, pty, select, time, re

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

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'
    os.environ['LINES'] = '24'
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.8); read_all(fd, 0.5)

# Type a command that will be in history for suggestions
os.write(fd, b'echo hello world\n')
time.sleep(0.6); read_all(fd, 0.3)

# Type partial command to trigger suggestion
os.write(fd, b'echo h')
time.sleep(1.5); read_all(fd, 0.3)

# Accept suggestion with Ctrl+F
os.write(fd, b'\x06')
time.sleep(0.5)
raw = read_all(fd, 0.3)

# Capture the display. Send Ctrl+L to get a clean redraw
os.write(fd, b'\x0c')  # Ctrl+L
time.sleep(0.5)
raw2 = read_all(fd, 0.5)

# The raw2 output is the redrawn screen after accept.
# The first line should be the prompt + buffer with NO color codes in the buffer portion.
text = raw2.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
lines = text.split('\n')

print("=== Screen after accept + Ctrl+L ===")
for i, l in enumerate(lines[:10]):
    clean = l.replace('\x1b', 'ESC')
    print(f"{i:2d}: {repr(clean)[:140]}")

# Check for color codes in the buffer area.
# After the prompt symbols (%, possibly colored), the buffer text should be plain.
# Specifically: there should be NO 'ESC[38;5;135m' or 'ESC[1m' AFTER the prompt
# and BEFORE the footer.

# Find the first prompt line (starts with %)
buffer_line = None
for l in lines:
    if '%' in l:
        buffer_line = l
        break

if buffer_line:
    # Strip the prompt portion (everything up to and including the prompt symbol + space)
    # The prompt is typically: ESC[1m%ESC[39m ESC[0m...
    # After that, the buffer text follows
    clean = buffer_line.replace('\x1b', 'ESC')
    # Find the position after prompt colors end and buffer text begins
    # Look for ESC[0m which resets all attributes (this is inserted after the prompt)
    reset_pos = clean.rfind('ESC[0m')
    if reset_pos >= 0:
        buffer_portion = clean[reset_pos:]
    else:
        buffer_portion = clean
    
    # Check if buffer portion contains color codes
    color_codes = re.findall(r'ESC\[[0-9;]*m', buffer_portion)
    # The only allowed code is ESC[0m (reset) at the start, and ESC[K (clear to EOL)
    disallowed = [c for c in color_codes if c not in ('ESC[0m', 'ESC[K', 'ESC[39m')]
    
    if disallowed:
        print(f"\n[FAIL] Color codes found in buffer area: {disallowed}")
        print(f"  Buffer portion: {buffer_portion[:120]}")
        success = False
    else:
        print(f"\n[PASS] No color codes in buffer area")
        success = True
else:
    print("\n[FAIL] No prompt line found")
    success = False

os.write(fd, b'exit\n'); time.sleep(0.2); os.close(fd); os.waitpid(pid, 0)
sys.exit(0 if success else 1)
