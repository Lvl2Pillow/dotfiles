# dotfiles
Personal .dotfiles and scripts managed by Chezmoi.

## Quick start
```sh
sh -c "$(curl -fsLS https://get.chezmoi.io)" -- init --apply https://github.com/Lvl2Pillow/dotfiles
```

## Features
- Idempotent scripts that installs tools and dependencies.
- Clean up script that removes stale target files.
- Custom ZSH prompt (<1ms to draw).
  - For large repos, relies on Git caches.
- Shell aliases and functions:
  - ls = colorful ls
  - o = open current directory or specified dir / file
  - fuck = [correct a typo](https://github.com/nvbn/thefuck)
- Git aliases:
  - alias = list all aliases with fzf
  - b = find and switch branch with fzf
  - l = readable log
  - amend = add more changes to last commit
  - uncommit = undo last commit
  - unstage = unstage (untrack for new files) all changes
  - jedi = force push

## Limitations
- Only battle-tested for MacOS.
