#!/usr/bin/env python3
"""Debug: show full output where permission denied appears."""
import os, pty, select, time, tempfile, shutil

tmp = tempfile.mkdtemp(prefix='zsh_')
repo = os.path.join(tmp, 'r')
os.makedirs(repo)
git_file = os.path.join(repo, '.git')
with open(git_file, 'w') as f:
    f.write('gitdir: /nonexistent/nope\n')
os.chmod(git_file, 0o000)

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'
    os.environ['LINES'] = '24'
    os.environ['TERM_PROGRAM'] = ''
    os.chdir(repo)
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.8)
out = b''
while True:
    r, _, _ = select.select([fd], [], [], 0.5)
    if not r:
        break
    try:
        chunk = os.read(fd, 8192)
        if not chunk:
            break
        out += chunk
    except OSError:
        break

text = out.decode('utf-8', errors='replace')
# Find all lines with 'permission'
for i, line in enumerate(text.split('\n')):
    if 'perm' in line.lower():
        print(f"  Line {i}: {line!r}")

# Also show the raw bytes around 'permission'
idx = text.lower().find('permission')
if idx >= 0:
    print(f"\n  Context around 'permission': {text[max(0,idx-50):idx+100]!r}")
else:
    # Check raw bytes
    idx2 = out.lower().find(b'permission')
    if idx2 >= 0:
        print(f"\n  Raw context: {out[max(0,idx2-50):idx2+100]!r}")
    else:
        print("\n  'permission' not found in any form")

os.write(fd, b'exit\n')
time.sleep(0.2)
os.close(fd)
os.waitpid(pid, 0)
try:
    os.chmod(git_file, 0o755)
except:
    pass
shutil.rmtree(tmp, ignore_errors=True)
