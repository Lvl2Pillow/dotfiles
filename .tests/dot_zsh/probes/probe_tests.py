#!/usr/bin/env python3
"""Probe which zsh file tests produce 'permission denied' errors."""
import os, pty, select, time, tempfile, shutil

def run(script):
    tmp = tempfile.mkdtemp(prefix='probe_')
    try:
        repo = os.path.join(tmp, 'r')
        os.makedirs(repo)
        os.system(f'cd {repo} && git init -q 2>/dev/null && git config user.email t@t 2>/dev/null && git config user.name t 2>/dev/null')
        os.chmod(os.path.join(repo, '.git'), 0o000)

        pid, fd = pty.fork()
        if pid == 0:
            os.environ['TERM'] = 'xterm-256color'
            os.environ['COLUMNS'] = '80'
            os.environ['LINES'] = '24'
            os.execvpe('zsh', ['zsh', '-c', f'cd {repo} && {script}'], os.environ)
            os._exit(1)

        time.sleep(0.5)
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
        os.close(fd)
        os.waitpid(pid, 0)
        return out.decode('utf-8', errors='replace')
    finally:
        try:
            os.chmod(os.path.join(repo, '.git'), 0o755) if os.path.exists(os.path.join(repo, '.git')) else None
        except:
            pass
        shutil.rmtree(tmp, ignore_errors=True)

tests = [
    ('[[ -d .git ]]', '[[ -d .git ]] 2>&1; echo "ex=$?"'),
    ('[[ -f .git/HEAD ]]', '[[ -f .git/HEAD ]] 2>&1; echo "ex=$?"'),
    ('< .git/HEAD (redirect)', '< .git/HEAD 2>&1; echo "ex=$?"'),
    ('read < .git/HEAD', 'IFS= read -r line < .git/HEAD 2>&1; echo "ex=$?"'),
]

for name, cmd in tests:
    out = run(cmd)
    print(f"=== {name} ===")
    print(out.strip()[:200])
    print()
