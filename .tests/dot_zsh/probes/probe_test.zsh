#!/usr/bin/env zsh
# Test which file tests produce "permission denied" in zsh
tmpdir=$(mktemp -d)
cd "$tmpdir"
git init -q 2>/dev/null
git config user.email t@t 2>/dev/null; git config user.name t 2>/dev/null
chmod 000 .git 2>/dev/null

echo "=== [[ -d .git ]] ==="
[[ -d .git ]] 2>&1; echo "ex=$?"

echo "=== [[ -f .git/HEAD ]] ==="
[[ -f .git/HEAD ]] 2>&1; echo "ex=$?"

echo "=== [[ -r .git/HEAD ]] ==="
[[ -r .git/HEAD ]] 2>&1; echo "ex=$?"

echo "=== < .git/HEAD ==="
< .git/HEAD 2>&1; echo "ex=$?"

chmod 755 .git
rm -rf "$tmpdir"
