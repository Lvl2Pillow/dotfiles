# List processes listening on a TCP port
check_port() {
    lsof -i "tcp:$1"
}

# Open current directory in Finder (or files with default app)
o() {
    if [ "$#" -eq 0 ]; then
        open .
    else
        open "$@"
    fi
}
