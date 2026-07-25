import pty, os, select, time, sys
sys.path.insert(0, '/tmp/pyte_venv/lib/python3.12/site-packages')
from pyte import Screen, Stream

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'
    os.environ['LINES'] = '24'
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.5)

def read_all(fd, t=0.5):
    data = b''
    while True:
        r, _, _ = select.select([fd], [], [], t)
        if not r: break
        try:
            chunk = os.read(fd, 4096)
            if not chunk: break
            data += chunk
        except: break
    return data

os.write(fd, b'_PROMPT_FORCE_LOAD=1 source ~/.zsh/05_prompt.zsh\n')
time.sleep(0.3)
out = read_all(fd, 0.4)

os.write(fd, b'\n')
time.sleep(0.3)
out += read_all(fd, 0.4)

os.write(fd, b'echo hi')
time.sleep(0.3)
out += read_all(fd, 0.4)

print("RAW OUTPUT (last 600 chars):")
print(out.decode('utf-8', errors='replace').replace('\x1b', '\\e')[-600:])

screen = Screen(24, 80)
stream = Stream(screen)
stream.feed(out.decode('utf-8', errors='replace'))
print("\nSCREEN LINES:")
for y in range(24):
    line = ''.join(screen.buffer[y][x].data for x in range(80)).rstrip()
    if line:
        print(f"{y}: {line!r}")

os.write(fd, b'exit\n')
time.sleep(0.2)
os.close(fd)
os.waitpid(pid, 0)
