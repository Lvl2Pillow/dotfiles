---
name: common-configure-chezmoi
description: Use when touching dotfiles, installing global tools/deps, or modifying config/dependency source code. Automates syncing all machines via chezmoi run_ scripts and managed files.
compatibility: opencode
---

# Chezmoi Configuration Management

Manage dotfiles and machine setup with [chezmoi](https://www.chezmoi.io/).

## When to use

- Dotfile edit (`~/.config/`, `~/.zshrc`, `~/.gitconfig`, etc.)
- Global tool/dep install (brew, npm -g, cargo, pipx, uv)
- Config/dependency source code changes that should be reproducible
- New machine bootstrap

Before acting, ask: _"Should this be same on all machines?"_ If yes, use this skill.

## 1. Before you start — read the docs

Fetch relevant doc page before making changes:

| Topic | URL |
|---|---|
| Scripts | https://www.chezmoi.io/user-guide/use-scripts-to-perform-actions/ |
| Templating | https://www.chezmoi.io/user-guide/templating/ |
| Encryption | https://www.chezmoi.io/user-guide/encryption/ |
| Include files from elsewhere | https://www.chezmoi.io/user-guide/include-files-from-elsewhere/ |
| Daily operations | https://www.chezmoi.io/user-guide/daily-operations/ |
| Reference — templates | https://www.chezmoi.io/reference/templates/ |
| Reference — special files/dirs | https://www.chezmoi.io/reference/special-files-and-directories/ |
| Reference — configuration file | https://www.chezmoi.io/reference/configuration-file/ |

## 2. Decision tree

| Scenario | Action |
|---|---|
| Edit config file (`.zshrc`, `kitty.conf`, `nvim/init.lua`) | `chezmoi add` → `chezmoi edit` for future changes |
| Install package/tool/global dep | Create `run_onchange_install-*.sh.tmpl` script |
| One-time setup action | Create `run_once_*.sh.tmpl` script |
| Include remote archive/git repo | Add to `.chezmoiexternal.{toml,yaml,json}` |
| Store secret (API key, cert, SSH key) | `chezmoi add --encrypt` with age |

For every manual change, **ask user** before creating a `run_` script. Explain what it does.

## 3. Target removal

Deleting from source dir does **not** remove target — file stays on disk. Always pair deletion with a `remove_` file so target gets cleaned on next `chezmoi apply`.

### Delete managed file

1. Remove source entry (e.g., `dot_bashrc`)
2. `touch ~/.local/share/chezmoi/remove_dot_bashrc`
3. `chezmoi diff` shows `remove .bashrc`
4. `chezmoi apply -n` to verify
5. Apply, commit both removal + `remove_` file

### Move / rename managed file

1. `chezmoi add ~/.newname` (creates `dot_newname` in source)
2. Remove `dot_oldname`
3. `touch remove_dot_oldname`
4. Diff shows `add .newname` + `remove .oldname`
5. `chezmoi apply -n`, apply, commit

### Notes

- `remove_` works on files, dirs, symlinks. Not on scripts (no target file).
- Dirs: `remove_dot_somedir` only removes if empty. Use `exact_` for full directory control.
- `remove_` files can be `.tmpl` templated for conditional removal.
- Keep `remove_` files until next apply confirms target gone, then commit.

## 4. File management

```bash
chezmoi add ~/.config/some/file
chezmoi add --template ~/.config/some/file   # per-machine variation
chezmoi add --encrypt ~/.ssh/id_ed25519       # secrets
chezmoi edit ~/.config/some/file
chezmoi diff
chezmoi apply -v
chezmoi chattr +template ~/.config/some/file  # mark as template retroactively
```

**Naming convention:**
- `~/.zshrc` → `dot_zshrc`
- `~/.config/kitty/kitty.conf` → `dot_config/kitty/kitty.conf`
- `~/.ssh/config` → `dot_ssh/config`
- Encrypted → `encrypted_` prefix, templates → `.tmpl` suffix

## 5. Script patterns

Scripts (`run_` prefix) execute during `chezmoi apply`, in alphabetical order.

### Prefix types

| Prefix | When to use |
|---|---|
| `run_` **(prefer)** | Idempotent script with "already done?" guard. Safe every apply. |
| `run_onchange_` | Non-idempotent or expensive (re-runs only on content change). |
| `run_once_` | One-off action, never re-run (use sparingly). |

**All scripts must be idempotent.** The guard inside the body makes `run_` safe — exits fast when nothing to do.

Use `before_` / `after_` for ordering: `run_once_before_install-pm.sh`.

### Examples

OS-conditional install (`run_onchange_install-packages.sh.tmpl`):
```bash
{{ if eq .chezmoi.os "linux" -}}
#!/bin/sh
sudo apt install ripgrep
{{ else if eq .chezmoi.os "darwin" -}}
#!/bin/sh
brew install ripgrep
{{ end -}}
```

Re-run when another file changes — embed its checksum:
```bash
{{- /* run_onchange_dconf-load.sh.tmpl */ -}}
#!/bin/bash
# hash: {{ include "dconf.ini" | sha256sum }}
dconf load / < {{ joinPath .chezmoi.sourceDir "dconf.ini" | quote }}
```

### Rules

- **All scripts must be idempotent.**
- `.tmpl` scripts: if template resolves to empty/whitespace, script is skipped.
- Place in `.chezmoiscripts/` to avoid target dir entries.
- No need to set executable bit.
- Must include `#!` line or be executable binary.
- Working dir: first existing parent in destination tree.
- `diff.exclude = ["scripts"]` in config to hide from `chezmoi diff`.
- **Never write dotfiles from scripts.** Dotfiles are managed directly. Scripts install tools and set env (eval, export). To update a dotfile, edit source file and let `chezmoi apply` handle it.

## 6. External files (`.chezmoiexternal.*`)

Pull files from remote sources without git submodules. Supports TOML, YAML, JSON; the file itself is a template.

```toml
# Archive
[".oh-my-zsh"]
    type = "archive"
    url = "https://github.com/ohmyzsh/ohmyzsh/archive/master.tar.gz"
    exact = true
    stripComponents = 1
    refreshPeriod = "168h"

# Single file
[".local/bin/rg"]
    type = "file"
    url = "https://github.com/BurntSushi/ripgrep/releases/download/14.1.0/rg-x86_64-apple-darwin"
    refreshPeriod = "168h"

# Git repo
[".vim/pack/plugin"]
    type = "git-repo"
    url = "https://github.com/alker0/chezmoi.vim.git"
    refreshPeriod = "168h"
```

**Caveats:**
- Large externals → use `run_onchange_` script instead (chezmoi validates external content on every diff/apply).
- Cache dirs from externals (e.g., `.oh-my-zsh/cache/completions/`) → add to `.chezmoiignore`.
- Git-repo externals: delegated to git, chezmoi cannot manage files inside them.

## 7. Template data

| Source | Example | Description |
|---|---|---|
| Automatic | `{{ .chezmoi.os }}` | OS, arch, hostname, username |
| Custom data | `{{ .chezmoidata.color_scheme }}` | From `.chezmoidata.{json,yaml,toml}` |
| Config file | `{{ .myvar }}` | `[data]` section in `chezmoi.toml` |
| Runtime prompt | `{{ promptStringOnce . "key" "Q?" }}` | Interactive prompt during init |
| Shared template | `{{ template "name" . }}` | Reusable from `.chezmoitemplates/` |

```bash
chezmoi data                          # view all template data
chezmoi execute-template '{{ .chezmoi.os }}'  # test snippet
```

## 8. Encryption

```bash
chezmoi agekey                         # generate age key
chezmoi add --encrypt ~/.ssh/id_ed25519
```
Config: `encryption = "age"` in `chezmoi.toml`.

Encrypted files get `encrypted_` attribute. Transparently decrypted during edit, encrypted during apply.

## 9. Verification workflow

**Never run `chezmoi apply` (without `-n`).** Only create scripts and dry-run. Let user review and apply.

1. `chezmoi diff` — show changes
2. **Ask user**: "Does this diff look right?"
3. `chezmoi apply -n` — dry-run only
4. **Stop.** Let user run `chezmoi apply`.
5. `chezmoi cd && git status` — review source changes
6. **Ask user**: "Commit and push?" (never auto-push per AGENTS.md)
7. Use descriptive commit message

## 10. Script state management

```bash
chezmoi state delete-bucket --bucket=entryState    # reset run_onchange_
chezmoi state delete-bucket --bucket=scriptState   # reset run_once_
```

## 11. Source directory layout

```
~/.local/share/chezmoi/
├── .chezmoiignore          # files/dirs chezmoi ignores
├── .chezmoiexternal.toml   # external dependencies
├── .chezmoiscripts/        # scripts (no target dir)
├── dot_config/             # ~/.config/*
├── dot_zshrc               # ~/.zshrc
├── dot_ssh/                # ~/.ssh/*
├── run_*.sh.tmpl           # scripts
└── README.md
```

## 12. Multi-repo setup (public + private)

When dotfiles need a public repo + a private override, run two independent chezmoi instances. Apply public first, then private — private files win.

### Architecture

```
~/.local/share/chezmoi-public/     # public repo
~/.local/share/chezmoi-private/    # private repo (overrides)
~/.config/chezmoi-public/chezmoi.toml
~/.config/chezmoi-private/chezmoi.toml
```

### Setup

```bash
# Public
chezmoi init https://github.com/you/dotfiles-public.git \
  --config ~/.config/chezmoi-public/chezmoi.toml \
  --source ~/.local/share/chezmoi-public

# Private
chezmoi init https://github.com/you/dotfiles-private.git \
  --config ~/.config/chezmoi-private/chezmoi.toml \
  --source ~/.local/share/chezmoi-private
```

Or `git clone` then `chezmoi init` per source dir.

### Daily apply

Shell function (in `~/.zshrc` or standalone script):

```bash
chezmoi-apply() {
    chezmoi apply \
      --config ~/.config/chezmoi-public/chezmoi.toml \
      --source ~/.local/share/chezmoi-public && \
    chezmoi apply \
      --config ~/.config/chezmoi-private/chezmoi.toml \
      --source ~/.local/share/chezmoi-private
}
```

Or a `run_chezmoi-apply.sh.tmpl` in the private repo for auto-run.

### What goes where

| Public | Private |
|---|---|
| `~/.zshrc`, `~/.gitconfig` | `~/.ssh/config` |
| `~/.config/nvim/` | Work gitconfig additions |
| Shell aliases, themes | Machine-specific config |
| Generic brew packages | API keys / certs (encrypted) |

### Caveats

- Each repo has independent config, templates, scripts, state DB.
- Scripts run twice (once per repo) — all must be idempotent.
- `chezmoi diff`/`status` covers one repo at a time.
- For secrets only, prefer encryption in a single repo over splitting.

## 13. Pitfalls

- **Scripts break declarative model.** Use sparingly; prefer managed files.
- **Always idempotent.** `run_once_`/`run_onchange_` state can be cleared.
- **No secrets in plaintext templates.** Use encryption or password manager (`pass`, `bitwarden`, `gopass`).
- **Large externals slow diff/apply.** Use `run_onchange_` script instead.
- **Externals with cache dirs** need `.chezmoiignore` entry, else every apply reports changes.
- **Template errors fail silently.** Always `chezmoi execute-template <file>` to verify.
- **Git-repo externals** need `git` on `$PATH`; chezmoi can't manage files inside cloned dir.
- **Script needs dotfile env vars** (e.g., `$PATH` from `~/.zshrc`): use `run_after_` prefix + **explicitly `source "$HOME/.zshrc"`** inside script. `run_after_` alone is insufficient.
- **Ask user** before creating `run_` script from a manual change.
