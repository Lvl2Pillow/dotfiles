#!/usr/bin/env python3
"""
RED test: _prompt_find_git must not emit "permission denied" when a
directory in the tree has .git as an unreadable file (git worktree).

The elif branch in _prompt_find_git does:
    IFS= read -r line < "$current/.git"

If .git is a file without read permission, zsh prints:
    "zsh: permission denied: /path/.git"

Test: create a directory with an unreadable .git file, cd into it,
verify no "permission denied" appears in prompt output.
"""
import os, sys, pty, select, time, tempfile, shutil

LINES = 24


def run_test():
    tmp = tempfile.mkdtemp(prefix='zsh_prompt_test_')
    try:
        # Create a fake git worktree: .git is a FILE (not directory)
        # pointing to a non-existent git dir. Make it unreadable.
        repo_dir = os.path.join(tmp, 'myrepo')
        os.makedirs(repo_dir)
        git_file = os.path.join(repo_dir, '.git')
        with open(git_file, 'w') as f:
            f.write('gitdir: /nonexistent/nope\n')
        os.chmod(git_file, 0o000)  # remove all permissions

        pid, fd = pty.fork()
        if pid == 0:
            os.environ['TERM'] = 'xterm-256color'
            os.environ['COLUMNS'] = '80'
            os.environ['LINES'] = str(LINES)
            os.environ['TERM_PROGRAM'] = ''
            os.chdir(repo_dir)
            os.execvpe('zsh', ['zsh', '-i'], os.environ)
            os._exit(1)

        time.sleep(0.8)

        # Trigger prompt redraw
        os.write(fd, b'\n')
        time.sleep(0.5)
        out = read_all(fd, 0.5)

        text = out.decode('utf-8', errors='replace')
        print(f"  Output (last 300 chars): {text[-300:]!r}")

        if 'permission denied' in text.lower() or 'Permission denied' in text:
            print("  [RED] 'permission denied' found — bug active")
            ok = False
        else:
            print("  [GREEN] No 'permission denied' — bug fixed")
            ok = True

        try:
            os.write(fd, b'exit\n')
            time.sleep(0.2)
            os.close(fd)
            os.waitpid(pid, 0)
        except Exception:
            pass

        return ok

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


if __name__ == '__main__':
    ok = run_test()
    status = 'PASS' if ok else 'FAIL'
    print(f'[{status}] _prompt_find_git does not emit permission denied on unreadable .git file')
    sys.exit(0 if ok else 1)
