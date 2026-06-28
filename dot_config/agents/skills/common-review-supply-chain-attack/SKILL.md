---
name: common-review-supply-chain-attack
description: Use when adding, installing, upgrading, or updating a dependency, plugin, package, or MCP server. Review risk of supply-chain attack and mitigate.
---

# Supply Chain Review

Review third-party dependencies (curl, brew, npm, yarn, pip, cargo, go mod, uv, opencode plugin, MCP server, etc.) that could silently introduce new vulnerabilities.

## Instructions

1. Before install
  - **Source**: Prefer packages with a public repo. Use checksum when available.
  - **Activity**: Check stars/commits/contributors/open issues. When only single maintainer, low activity, or sloppy code, then flag as high risk.
  - **Dependency tree**: `npm ls` / `pip-audit` / equivalent. Flag transitive dependencies that you don't recognize or that look typosquatted.
  - **Scope**: Does it actually need the permissions that it is asking for?

2. If the dependency is high risk, then notify the user and ask for confirmation before continuing.

3. Install
  - **Pin exact version** (e.g. `pkg@1.70.0`), never `latest`/`^` for untrusted dependencies.
  - **Disable auto-update** for untrusted deps (opencode: `autoupdate: "notify"` or `false`).
  - **Commit the lockfile** (`package-lock.json`/`poetry.lock`/etc.) so CI resolves identical.
