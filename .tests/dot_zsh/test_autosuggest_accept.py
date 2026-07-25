#!/usr/bin/env python3
"""
RED test: After typing partial command, ghost text appears.
Press Ctrl+F (forward-char) to accept suggestion.
Verify: no double footer, buffer contains full command.
"""
import os, pty, select, time, re

LINES = 24

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            break
        try:
            chunk = os.read(fd, 8192)
            if not chunk:
                break
            out += chunk
        except OSError:
            break
    return out

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'
    os.environ['LINES'] = str(LINES)
    os.environ['TERM_PROGRAM'] = ''
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.8)
read_all(fd, 0.5)

# Add command to history
os.write(fd, b'echo hello world\n')
time.sleep(0.5)
read_all(fd, 0.3)

# Type partial command
os.write(fd, b'echo h')
time.sleep(1.5)
read_all(fd, 0.3)

# How many footers visible BEFORE accept?
os.write(fd, b'\x0c')  # Ctrl+L to clear and see state before
time.sleep(0.3)
before = read_all(fd, 0.3)

clean_before = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', before.decode('utf-8', errors='replace'))
clean_before = clean_before.replace('\r', '').replace('\x1b', '')
rows_before = [l.strip() for l in clean_before.split('\n') if l.strip()]
print("BEFORE accept:")
for i, row in enumerate(rows_before):
    print(f"  [{i}] {row!r}")
footers_before = [r for r in rows_before if not r.startswith('%') and ('.' in r or '/' in r)]
print(f"  Footer count before: {len(footers_before)}")

# Now accept the suggestion with Ctrl+F (forward-char)
os.write(fd, b'\x06')  # Ctrl+F
time.sleep(1.0)
read_all(fd, 0.3)

# Capture screen after accept
os.write(fd, b'\x0c')  # Ctrl+L
time.sleep(0.3)
after = read_all(fd, 0.3)

clean_after = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', after.decode('utf-8', errors='replace'))
clean_after = clean_after.replace('\r', '').replace('\x1b', '')
rows_after = [l.strip() for l in clean_after.split('\n') if l.strip()]
print("\nAFTER accept (Ctrl+F then Ctrl+L):")
for i, row in enumerate(rows_after):
    print(f"  [{i}] {row!r}")

# Find prompt row and footer rows
prompt_rows = [r for r in rows_after if r.startswith('%') or r.startswith('#')]
footer_rows = [r for r in rows_after if not r.startswith('%') and not r.startswith('#') and ('.' in r or '/' in r or '~' in r)]

print(f"\nPrompt: {prompt_rows}")
print(f"Footer rows: {footer_rows}")

# Check conditions
if len(footer_rows) > 1:
    print(f"[RED] Double footer: {len(footer_rows)} footer lines (expected 1)")
else:
    print(f"[GREEN] Footer count OK: {len(footer_rows)}")

# Check buffer content
if prompt_rows:
    buf = prompt_rows[0].lstrip('%# ').strip()
    print(f"Buffer content: {buf!r}")
    if 'hello world' in buf:
        print(f"[GREEN] Full command 'echo hello world' in buffer")
    elif 'hello' in buf:
        print(f"[GREEN] Partial command with 'hello' in buffer")
    else:
        print(f"[RED] Buffer content unexpected: {buf!r}")
    # Check for footer contamination
    if '\\n' in buf or (('~/' in buf or '/' in buf) and len(buf) > 20):
        print(f"[RED] Buffer may contain footer text: {buf!r}")

os.write(fd, b'exit\n')
time.sleep(0.2)
os.close(fd)
os.waitpid(pid, 0)
