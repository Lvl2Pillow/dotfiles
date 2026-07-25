#!/usr/bin/env zsh
# Probe: does [[ -f path ]] print "permission denied" in zsh when .git/HEAD is inaccessible?
setopt extended_glob
tmpdir=$(mktemp -d)
cd "$tmpdir"
git init 2>/dev/null
git config user.email t@t 2>/dev/null
git config user.name t 2>/dev/null
chmod 000 .git 2>/dev/null

echo "=== Testing [[ -d .git ]] ==="
[[ -d .git ]] 2>&1 && echo "exit: $? (dir exists)" || echo "exit: $? (dir check failed)"

echo "=== Testing [[ -f .git/HEAD ]] ==="
[[ -f .git/HEAD ]] 2>&1 && echo "exit: $? (file exists)" || echo "exit: $? (file check failed)"

echo "=== Testing stat directly ==="
stat -f '%N' .git/HEAD 2>&1 || true

chmod 755 .git 2>/dev/null
echo "=== Done ==="
rm -rf "$tmpdir"
