---
name: common-configure-chezmoi
description: Use when touching dotfiles, installing global tools/deps, or modifying config/dependency source code. Automates syncing all machines via chezmoi run_ scripts and managed files.
compatibility: opencode
---

# Chezmoi Configuration Management

Manage dotfiles and machine setup reproducibly with [chezmoi](https://www.chezmoi.io/).

## When to use

- Touching any dotfile in `~/.config/`, `~/.zshrc`, `~/.gitconfig`, etc.
- Installing global tools/deps (brew, npm -g, cargo install, pipx, uv tool, etc.)
- Manually modifying config or dependency source code that should be reproducible
- Setting up a new machine / bootstrapping

Before acting, ask: _"Is this something that should be the same on all my machines?"_ If yes, use this skill.

## 1. Before you start — read the docs

Fetch the relevant chezmoi doc page before making changes. Key URLs:

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

Always read the most relevant page before writing scripts or templates.

## 2. Decision tree: managed file vs script

| Scenario | Action |
|---|---|
| Editing a config file (`.zshrc`, `kitty.conf`, `nvim/init.lua`) | `chezmoi add` it, then `chezmoi edit` for future changes |
| Installing a package/tool/global dep | Create a `run_onchange_install-*.sh.tmpl` script |
| Running a one-time setup action | Create a `run_once_*.sh.tmpl` script |
| Including a remote archive / git repo | Add entry in `.chezmoiexternal.{toml,yaml,json}` |
| Storing a secret (API key, cert, SSH key) | `chezmoi add --encrypt` with age |
| Manually editing a config that was already a raw file | Ask user: "Should I convert this to a chezmoi managed file or a run_ script?" |

**Important:** For every manual change, ask the user before creating a run_ script. Explain what it will do.

## 3. Target removal

By default, chezmoi does **not** remove target files when you delete entries from the source directory — it only stops managing them. The file stays on disk unchanged.

**Our convention:** always clean up targets. When you delete or move a file in the source state, create a `remove_` file for the old location so the target is removed on the next `chezmoi apply`.

### Delete a managed file (remove from home dir too)

1. Remove the source entry (e.g., `dot_bashrc`) from the source directory
2. Create an empty `remove_dot_bashrc` file alongside:
   ```
   touch ~/.local/share/chezmoi/remove_dot_bashrc
   ```
3. `chezmoi diff` shows: `remove .bashrc`
4. `chezmoi apply -n` to verify
5. Apply, then commit both the deletion and the `remove_` file together

### Move / rename a managed file

1. `chezmoi add ~/.newname` — creates `dot_newname` in source
2. Remove `dot_oldname` from source
3. Create empty `remove_dot_oldname`
4. Diff shows: `add .newname` + `remove .oldname`
5. Verify with `chezmoi apply -n`, then apply and commit

### Notes

- `remove_` works on files, directories, and symlinks. It does **not** work on scripts (scripts have no target file).
- For directories: `remove_dot_somedir` only removes the directory if it is empty. To fully control a directory's contents (including removing unmanaged files), use `exact_` instead.
- The `remove_` file itself can be `.tmpl` templated (e.g., `remove_dot_bashrc.tmpl`) if the removal should be conditional on some template variable.
- Keep `remove_` files in source until the next apply confirms the target is gone, then commit them as part of the same change.

## 4. File management

```bash
# Add a file to chezmoi management
chezmoi add ~/.config/some/file

# Add as a template (so it can vary per machine)
chezmoi add --template ~/.config/some/file

# Add with encryption (for secrets)
chezmoi add --encrypt ~/.ssh/id_ed25519

# Edit the source copy
chezmoi edit ~/.config/some/file

# Review pending changes
chezmoi diff

# Apply changes to home directory
chezmoi apply -v

# Mark existing managed file as template
chezmoi chattr +template ~/.config/some/file
```

**Naming convention in source dir:**
- `~/.zshrc` → `dot_zshrc`
- `~/.config/kitty/kitty.conf` → `dot_config/kitty/kitty.conf`
- `~/.ssh/config` → `dot_ssh/config`
- Encrypted files get `encrypted_` prefix, templates get `.tmpl` suffix

## 5. Script patterns

Scripts are files with a `run_` prefix in the source directory. They execute during `chezmoi apply`.

### Prefix types (prefer `run_`)

| Prefix | When to use |
|---|---|
| `run_` **(prefer)** | Idempotent scripts that check "already done?" before acting. Safe to re-run every `chezmoi apply`. |
| `run_onchange_` | Non-idempotent or expensive scripts (only re-run when content changes). |
| `run_once_` | One-off actions that must never re-run (use sparingly). |

**All scripts must be idempotent.** The check for "already installed / already done" lives inside the script body, so `run_` is safe — it exits fast when nothing needs doing.

Use `before_` / `after_` attributes to control ordering, e.g., `run_once_before_install-password-manager.sh`.

### OS-conditional package install

```bash
# ~/.local/share/chezmoi/run_onchange_install-packages.sh.tmpl
{{ if eq .chezmoi.os "linux" -}}
#!/bin/sh
sudo apt install ripgrep fzf
{{ else if eq .chezmoi.os "darwin" -}}
#!/bin/sh
brew install ripgrep fzf
{{ end -}}
```

### Re-run when another file changes

```bash
{{- /* ~/.local/share/chezmoi/run_onchange_dconf-load.sh.tmpl */ -}}
#!/bin/bash

# dconf.ini hash: {{ include "dconf.ini" | sha256sum }}
dconf load / < {{ joinPath .chezmoi.sourceDir "dconf.ini" | quote }}
```

### Script rules

- **All scripts must be idempotent** (safe to run multiple times).
- Scripts with `.tmpl` suffix are executed as templates first. If they resolve to empty/whitespace, they are skipped.
- Place scripts in `.chezmoiscripts/` directory to avoid creating corresponding target directories.
- No need to set executable bit — chezmoi handles it.
- Scripts must include a `#!` line or be executable binaries.
- Working directory is set to the first existing parent in the destination tree.
- Use `diff.exclude = ["scripts"]` in config to hide script contents from `chezmoi diff`.
- **Never write dotfiles from scripts.** Dotfiles (`~/.zshrc`, `~/.zprofile`, `~/.config/*`, etc.) are managed directly by chezmoi. Scripts install tools and set up the environment for the current process (`eval`, `export`). If a dotfile needs updating, modify the source file and `chezmoi apply` handles it.

## 6. External files (`.chezmoiexternal.*`)

Use when you need to include files from remote sources (not git submodules).

```toml
# ~/.local/share/chezmoi/.chezmoiexternal.toml

# Archive (e.g., oh-my-zsh)
[".oh-my-zsh"]
    type = "archive"
    url = "https://github.com/ohmyzsh/ohmyzsh/archive/master.tar.gz"
    exact = true
    stripComponents = 1
    refreshPeriod = "168h"

# Single file
[".local/bin/ripgrep"]
    type = "file"
    url = "https://github.com/BurntSushi/ripgrep/releases/download/14.1.0/rg-x86_64-apple-darwin"
    refreshPeriod = "168h"

# Git repo
[".vim/pack/alker0/chezmoi.vim"]
    type = "git-repo"
    url = "https://github.com/alker0/chezmoi.vim.git"
    refreshPeriod = "168h"
```

Supported formats: TOML, YAML, JSON. The file is also a template (supports `.tmpl` syntax).

**Caveats:**
- Large externals should use `run_onchange_` scripts instead (chezmoi validates external content on every diff/apply).
- Cache directories produced by externals (e.g., `.oh-my-zsh/cache/completions/`) must be added to `.chezmoiignore`.
- Git-repo externals are delegated to git — chezmoi cannot manage files inside them.

## 7. Template data and variables

| Source | Example | Description |
|---|---|---|
| Automatic | `{{ .chezmoi.os }}` | OS, arch, hostname, username, etc. |
| Custom data | `{{ .chezmoidata.color_scheme }}` | From `.chezmoidata.{json,yaml,toml}` |
| Config file | `{{ .myvar }}` | From `[data]` section in `chezmoi.toml` |
| Runtime prompt | `{{ promptStringOnce . "key" "Question?" }}` | Interactive prompt during init |
| Shared template | `{{ template "name" . }}` | Reusable snippet from `.chezmoitemplates/` |

```bash
# View all available template data
chezmoi data

# Test a template snippet
chezmoi execute-template '{{ .chezmoi.os }}'
```

## 8. Encryption

```bash
# Generate age key if not already set up
chezmoi agekey

# Add an encrypted file
chezmoi add --encrypt ~/.ssh/id_ed25519

# Config (chezmoi.toml)
encryption = "age"
```

Encrypted files get the `encrypted_` attribute. They are transparently decrypted/encrypted during `chezmoi edit` and `chezmoi apply`.

## 9. Verification workflow

**Never run `chezmoi apply` (without `-n`).** Only create scripts and dry-run. Let the user review and apply manually.

Always follow this sequence:

1. `chezmoi diff` — show what will change
2. **Ask user**: "Does this diff look right?" before applying
3. `chezmoi apply -n` — **dry-run only**. Show the output to the user.
4. **Stop.** Let the user review everything and run `chezmoi apply` themselves.
5. `chezmoi cd && git status` — review source directory changes
6. **Ask user**: "Commit and push?" (never auto-push per AGENTS.md)
7. When committing, use a descriptive message matching the change

## 10. Run script state management

```bash
# Reset run_onchange_ scripts (force re-run on next apply)
chezmoi state delete-bucket --bucket=entryState

# Reset run_once_ scripts (force re-run on next apply)
chezmoi state delete-bucket --bucket=scriptState
```

## 11. Source directory layout

```
~/.local/share/chezmoi/
├── .chezmoiignore          # files/dirs chezmoi should not manage
├── .chezmoiexternal.toml   # external dependencies
├── .chezmoiscripts/        # scripts without target dir entries
├── dot_config/             # ~/.config/*
├── dot_zshrc               # ~/.zshrc
├── dot_ssh/                # ~/.ssh/*
├── run_*.sh.tmpl           # scripts (with optional templates)
└── README.md
```

## 12. Pitfalls

- **Scripts break the declarative model.** Use them sparingly. Prefer managed files.
- **Always make scripts idempotent.** `run_once_` and `run_onchange_` can get their state cleared.
- **Never put secrets in plaintext templates.** Use encryption or a password manager (`pass`, `bitwarden`, `gopass`).
- **Large externals cause slow diff/apply.** Use `run_onchange_` scripts for big archives.
- **Externals with cache dirs need `.chezmoiignore` entries.** Otherwise every `chezmoi apply` reports changes.
- **Template errors fail silently.** Always test with `chezmoi execute-template <file>`.
- **Git-repo externals need `git` on `$PATH`.** They also prevent chezmoi from managing files inside the cloned dir.
- **Script ordering vs dotfile env vars.** If a script needs environment variables set in a managed dotfile (e.g., `$PATH` from `~/.zshrc`), it must use the `run_after_` prefix (so dotfiles are applied first) and **explicitly source** the dotfile inside the script: `source "$HOME/.zshrc"`. Without sourcing, the variable may not be available even with `run_after_`.
- **Always verify with the user** before creating a `run_` script from a manual change.
