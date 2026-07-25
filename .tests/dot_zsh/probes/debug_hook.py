import pty, os, select, time

# Clear debug log
with open('/tmp/prompt_debug.log', 'w') as f:
    pass

pid, fd = pty.fork()
if pid == 0:
    os.environ['TERM'] = 'xterm-256color'
    os.environ['COLUMNS'] = '80'
    os.environ['LINES'] = '24'
    os.execvpe('zsh', ['zsh', '-i'], os.environ)
    os._exit(1)

time.sleep(0.5)
def read_all(fd, t=0.4):
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
read_all(fd, 0.3)
os.write(fd, b'\n')
time.sleep(0.3)
read_all(fd, 0.3)

os.write(fd, b'echo ')
long = 'a' * 160
os.write(fd, long.encode())
time.sleep(0.7)
read_all(fd, 0.7)

os.write(fd, b'\n')
time.sleep(0.3)
read_all(fd, 0.3)
os.write(fd, b'exit\n')
time.sleep(0.3)
os.close(fd)
os.waitpid(pid, 0)
