"""
RED test: Verify that _prompt_zle_append_footer SKIPS during accept-line
(no footer appended while line is being accepted).

The WIDGET check should cause SKIP_ACCEPT for all accept-line entries,
preventing the double-footer bug.
"""
import os, sys, pty, select, time, glob

def read_all(fd, timeout=0.5):
    out = b''
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: break
        try: c = os.read(fd, 8192); out += c
        except: break
    return out

def run_probe(config, keystrokes=b''):
    for f in glob.glob('/tmp/widget_log.*'): os.unlink(f)
    pid, fd = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLUMNS'] = '80'; os.environ['LINES'] = '24'
        d = f'/tmp/zsh_probe_{os.getpid()}'; os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, '.zshrc'), 'w') as f: f.write(config + '\n')
        os.environ['ZDOTDIR'] = d
        os.execvpe('zsh', ['zsh', '-i'], os.environ); os._exit(1)
    time.sleep(1.5); read_all(fd, 0.3)
    if keystrokes:
        os.write(fd, keystrokes)
        time.sleep(0.5)
        read_all(fd, 0.3)
    logs = sorted(glob.glob('/tmp/widget_log.*'))
    lines = []
    for log in logs:
        with open(log) as f:
            lines.extend(f.read().splitlines())
        os.unlink(log)
    os.close(fd); os.waitpid(pid, 0)
    return lines

def probe_append_call_count(enter=b'\n'):
    config = r'''
source ~/.zshrc 2>/dev/null || true
_logfile=/tmp/widget_log.$$
_pmlog() { echo "$1" >> $_logfile; }
_prompt_zle_append_footer() {
  emulate -L zsh
  _pmlog "WIDGET=[$WIDGET]"
  [[ -z "$_prompt" ]] && { _pmlog "SKIP_NOPROMPT"; return 0; }
  zle 2>/dev/null && ZV=Y || ZV=N
  _pmlog "ZLE=$ZV"
  [[ $ZV = N ]] && { _pmlog "SKIP_NOZLE"; return 0; }
  [[ $WIDGET = *accept-line* ]] && { _pmlog "SKIP_ACCEPT"; return 0; }
  _pmlog "APPEND"
  return 0
}
'''
    return run_probe(config, keystrokes=enter)

def test_accept_line_always_skips():
    """Every accept-line call must result in SKIP_ACCEPT, never APPEND."""
    lines = probe_append_call_count(b'\n')
    errors = []
    for i, l in enumerate(lines):
        if l.startswith('WIDGET=['):
            # Check the next ACTION lines
            pass
        if l == 'APPEND':
            # Find the WIDGET before this APPEND
            for j in range(i-1, -1, -1):
                if lines[j].startswith('WIDGET=['):
                    widget = lines[j]
                    if 'accept-line' in widget:
                        errors.append(f'APPEND during accept-line at entry {j}: {lines[j]}')
                    break

    # Also check: every time WIDGET matches accept-line, the next action is SKIP_ACCEPT
    for i, l in enumerate(lines):
        if l.startswith('WIDGET=[') and 'accept-line' in l:
            # Find the next action line (SKIP_* or APPEND)
            for j in range(i+1, min(i+5, len(lines))):
                if lines[j] in ('SKIP_NOPROMPT', 'SKIP_NOZLE', 'SKIP_ACCEPT', 'APPEND'):
                    if lines[j] != 'SKIP_ACCEPT':
                        errors.append(f'Expected SKIP_ACCEPT after {l}, got {lines[j]}')
                    break

    if errors:
        return False, f'{len(errors)} errors: ' + '; '.join(errors[:3])
    return True, f'All accept-line calls correctly skipped'

def test_at_least_one_append_after():
    """At least one APPEND happens after the first accept-line (for new prompt)."""
    lines = probe_append_call_count(b'\n')
    # Find first accept-line
    first_accept_idx = None
    for i, l in enumerate(lines):
        if l.startswith('WIDGET=[') and 'accept-line' in l:
            first_accept_idx = i
            break
    if first_accept_idx is None:
        return False, 'No accept-line call found'

    # Check for APPEND after first accept-line
    found_append = False
    for i in range(first_accept_idx + 1, len(lines)):
        if lines[i] == 'APPEND':
            found_append = True
            break
    if not found_append:
        return False, 'No APPEND after first accept-line'
    return True, f'Found APPEND after accept-line'

def test_no_extra_append_after_last_zle_init():
    """No APPEND calls happen after the last zle-line-init APPEND pair."""
    lines = probe_append_call_count(b'\n')
    # Find the LAST occurrence of WIDGET=[zle-line-init] followed by APPEND
    last_append_idx = -1
    for i in range(len(lines)-1, -1, -1):
        if lines[i] == 'APPEND':
            # Check if preceded by zle-line-init
            for j in range(i-1, -1, -1):
                if lines[j].startswith('WIDGET=['):
                    if 'zle-line-init' in lines[j]:
                        last_append_idx = i
                    break
            if last_append_idx == i:
                break

    if last_append_idx == -1:
        return False, 'No zle-line-init APPEND found'

    # Any APPEND after last_append_idx?
    extra_appends = sum(1 for l in lines[last_append_idx+1:] if l == 'APPEND')
    if extra_appends > 0:
        return False, f'{extra_appends} extra APPEND calls after last zle-line-init'
    return True, 'No extra APPEND after last zle-line-init'

if __name__ == '__main__':
    tests = [
        ('accept-line always skips', test_accept_line_always_skips),
        ('at least one APPEND after accept-line', test_at_least_one_append_after),
        ('no extra APPEND after last zle-line-init', test_no_extra_append_after_last_zle_init),
    ]
    pass_count = 0
    fail_count = 0
    for name, fn in tests:
        ok, msg = False, 'exception'
        try: ok, msg = fn()
        except Exception as e: msg = str(e)
        if ok:
            pass_count += 1; print(f'  PASS: {name}')
        else:
            fail_count += 1; print(f'  FAIL: {name} — {msg}')
    print(f'\n{pass_count}/{pass_count + fail_count} passed')
    sys.exit(0 if fail_count == 0 else 1)
