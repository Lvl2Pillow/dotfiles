#!/usr/bin/env python3
"""Probe: does zsh [[ -f path ]] print permission denied when .git/HEAD is inaccessible?"""
import os, pty, select, time, tempfile, shutil

def read_all(fd, timeout=1.0):
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

tmp = tempfile.mkdtemp(prefix='probe_')
repo = os.path.join(tmp, 'r')
os.makedirs(repo)
os.system(f'cd {repo} && git init -q 2>/dev/null && git config user.email t@t 2>/dev/null && git config user.name t 2>/dev/null')
os.chmod(os.path.join(repo, '.git'), 0o000)

cmd = f'cd {repo} && zsh -c \'mention() {{ mention_ok=1; }}; [[ -d .git ]] 2>&1; echo "d=$?"; [[ -f .git/HEAD ]] 2>&1; echo "f=$?"; echo DONE\''

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'
    os.environ['LINES'] = '10'
    os.execvpe('zsh', ['zsh', '-c', f'cd {repo} && [[ -d .git ]]; echo "d=$?"; [[ -f .git/HEAD ]] 2>&1; echo "f=$?"; echo DONE'], os.environ)
    os._exit(1)

time.sleep(0.5)
out = read_all(fd, 1.0)
print(out.decode('utf-8', errors='replace'))

try:
    os.chmod(os.path.join(repo, '.git'), 0o755)
except:
    pass
shutil.rmtree(tmp, ignore_errors=True)
