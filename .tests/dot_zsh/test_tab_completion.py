#!/usr/bin/env python3
"""
Completion-list placement vs the transient footer (05_prompt.zsh).

Bug: zle draws the completion list below the whole line (POSTDISPLAY included),
so with the footer in POSTDISPLAY the list landed underneath it. Fix: the
completion widgets are wrapped to hide the footer before the list renders, and
the footer is restored as soon as a non-completion widget runs (zle invalidates
the list for every non-menu widget). Two follow-up bugs are covered too:

  * multi-line lists: on dismissal zle only clears the list area when clearlist
    is set, so stale suggestion rows lingered below the footer; the fix runs
    `zle -R -c` (clear the completion list) on dismissal.
  * "do you wish to see all N possibilities? [y/n]": asked when the list is
    bigger than the screen; the question must appear under the buffer with the
    footer hidden, and the stale list rows must clear after answering.

Asserts, in a real zsh inside a PTY (needs openpty, so run outside the
sandbox):
  001 footer visible under buffer before Tab
  002 single-row list directly under buffer, footer hidden
  003 typing: footer restored, list gone
  004 multi-line list directly under buffer, footer hidden
  005 typing: footer at row 1, rows below cleared (no stale suggestions)
  006 too-many-suggestions: y/n question under buffer, footer hidden
  007 answering 'y' displays the list
  008 typing after 'y': footer restored, no stale rows
  009 answering 'n' hides the question (footer returns on next keypress)
  010 typing after 'n': footer restored

Run: python3 .tests/dot_zsh/test_tab_completion.py
"""
import os, sys, pty, select, time, shutil, struct, fcntl, termios

from miniterm import MiniTerm

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            break
        try:
            c = os.read(fd, 8192)
            if not c:
                break
            out += c
        except Exception:
            break
    return out

def wait_for_prompt(fd, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            return True
    return False

PROMPT_SRC = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'dot_zsh', '05_prompt.zsh'))

def run():
    workdir = f'/tmp/zsh_tabtest_{os.getpid()}'
    os.makedirs(workdir, exist_ok=True)

    pid, fd = pty.fork()
    if pid:
        # Pin the pty window size so zsh's zterm_lines/zterm_columns match the
        # MiniTerm model (10 rows is what triggers the y/n question below).
        # (In the child pty.fork() returns fd=-1, so this must not run there.)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 10, 80, 0, 0))
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'
        os.environ['LINES'] = '10'
        d = f'/tmp/zsh_probe_{os.getpid()}'
        os.makedirs(d, exist_ok=True)
        def wcmd(name, words):
            return (f'_comp_{name}() {{ compadd {" ".join(words)} }}\n'
                    f'compdef _comp_{name} {name}\n')
        # Distinct first letters: no common prefix, so the list shows on the
        # first Tab instead of just inserting a prefix.
        many = [f'{c}{i}' for c in 'fgh' for i in range(1, 10)]      # 27 words -> 2 rows
        longw = [chr(ord('a') + i) + 'x' * 59 for i in range(12)]    # 60 cols, 1/row, 12 rows
        cfg = (
            'setopt no_beep autolist\n'
            'unset LISTMAX\n'   # parent env exports LISTMAX=100; unset so the
                                # y/n question fires via list lines >= screen
            'autoload -Uz compinit\n'
            'compinit -u\n'
            + wcmd('testcmd', ['one', 'two', 'three', 'four', 'five'])
            + wcmd('manycmd', many)
            + wcmd('longcmd', longw)
            + f'cd {workdir}\n'
            + f'source {PROMPT_SRC}\n'
        )
        with open(os.path.join(d, '.zshrc'), 'w') as f:
            f.write(cfg)
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ)
        os._exit(1)

    results = []
    all_data = b''

    def snap():
        """Replay the whole session stream into a fresh terminal model."""
        term = MiniTerm(80, 10)
        term.feed(all_data)
        return term

    def drain():
        nonlocal all_data
        all_data += read_all(fd, 0.3)

    def send(data, wait=0.4):
        os.write(fd, data)
        time.sleep(wait)
        drain()

    def new_line():
        """Discard the current buffer (Ctrl+C) and normalize the screen so the
        prompt is at row 0 with the footer at row 1 (Ctrl+L)."""
        send(b'\x03')
        send(b'\x0c')

    try:
        wait_for_prompt(fd, 8.0)
        drain()
        new_line()

        # --- 001: footer under buffer before Tab ---
        send(b'testcmd ')
        term = snap()
        ok = workdir in term.display[1]
        results.append(('001 footer under buffer', ok,
                        f'row1={term.display[1]!r}'))

        # --- 002: Tab -> single-row list under buffer, footer hidden ---
        send(b'\t', 0.5)
        term = snap()
        ok = ('one' in term.display[1]
              and all(workdir not in r for r in term.display))
        results.append(('002 single-row list under buffer, footer hidden', ok,
                        f'row1={term.display[1]!r}'))

        # --- 003: typing dismisses list, footer restored ---
        send(b'x')
        term = snap()
        ok = (workdir in term.display[1]
              and all('one' not in r for r in term.display))
        results.append(('003 typing restores footer, list gone', ok,
                        f'row1={term.display[1]!r}'))

        # --- 004: multi-line list under buffer, footer hidden ---
        new_line()
        send(b'manycmd ')
        term = snap()
        ok = workdir in term.display[1]
        results.append(('004a footer under buffer (manycmd)', ok,
                        f'row1={term.display[1]!r}'))
        send(b'\t', 0.5)
        term = snap()
        list_rows = [i for i in range(1, 10) if any(w in term.display[i] for w in ('f1', 'g1', 'h1'))]
        ok = (len(list_rows) >= 2
              and all(workdir not in r for r in term.display))
        results.append(('004b multi-line list under buffer, footer hidden', ok,
                        f'list_rows={list_rows} row1={term.display[1]!r}'))

        # --- 005: typing clears stale list rows below the footer ---
        send(b'x')
        term = snap()
        stale = [i for i in range(2, 10)
                 if any(w in term.display[i] for w in ('f1', 'g1', 'h1'))]
        ok = (workdir in term.display[1] and not stale)
        results.append(('005 typing clears stale list rows below footer', ok,
                        f'stale_rows={stale} row1={term.display[1]!r}'))

        # --- 006: too many suggestions -> y/n question under buffer ---
        new_line()
        send(b'longcmd ')
        send(b'\t', 0.6)
        term = snap()
        ok = ('do you wish' in term.display[1]
              and all(workdir not in r for r in term.display))
        results.append(('006 y/n question under buffer, footer hidden', ok,
                        f'row1={term.display[1]!r}'))

        # --- 007: answer 'y' -> answer consumed, question cleared ---
        # (the 12-line list scrolls a 10-row screen, so only assert the
        # question is gone and 'y' was not typed into the buffer)
        send(b'y', 0.6)
        term = snap()
        ok = (all('do you wish' not in r for r in term.display)
              and all(' longcmd y' not in r for r in term.display))
        results.append(('007 y consumed by question, question cleared', ok,
                        'question still visible or y typed into buffer'))

        # --- 008: typing after 'y' -> footer restored, no stale rows ---
        mark = 'a' + 'x' * 10      # distinctive start of the first long word
        send(b'x')
        term = snap()
        ok = (any(workdir in r for r in term.display)
              and all(mark not in r for r in term.display)
              and all('do you wish' not in r for r in term.display))
        results.append(('008 typing after y restores footer, no stale rows', ok,
                        f'footer_found={any(workdir in r for r in term.display)}'))

        # --- 009: answer 'n' -> question dismissed (footer returns on next key) ---
        new_line()
        send(b'longcmd ')
        send(b'\t', 0.6)
        term = snap()
        ok = 'do you wish' in term.display[1]
        results.append(('009a y/n question shown again', ok,
                        f'row1={term.display[1]!r}'))
        send(b'n', 0.5)
        term = snap()
        q_gone = all('do you wish' not in r for r in term.display)
        results.append(('009b question gone after n', q_gone,
                        'question text still visible'))

        # --- 010: typing after 'n' -> footer restored ---
        send(b'x')
        term = snap()
        ok = workdir in term.display[1]
        results.append(('010 typing after n restores footer', ok,
                        f'row1={term.display[1]!r}'))

    finally:
        os.write(fd, b'\x03')          # Ctrl+C to clear the buffer
        time.sleep(0.2)
        os.write(fd, b'exit\n')
        time.sleep(0.3)
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.waitpid(pid, 0)
        except OSError:
            pass
        shutil.rmtree(workdir, ignore_errors=True)

    return results

if __name__ == '__main__':
    fail_count = 0
    pass_count = 0
    for name, ok, msg in run():
        if ok:
            pass_count += 1
            print(f'  PASS: {name}')
        else:
            fail_count += 1
            print(f'  FAIL: {name} — {msg}')
    print(f'\n{pass_count}/{pass_count + fail_count} passed')
    sys.exit(0 if fail_count == 0 else 1)
