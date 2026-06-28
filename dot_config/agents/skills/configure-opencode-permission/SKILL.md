---
name: configure-opencode-permission
description: "Reference for configuring OpenCode permissions."
compatibility: opencode
---

## Instructions

1. Read the official documentation from https://opencode.ai/docs/permissions/.
2. Read the existing permissions in ~/.config/opencode/
  - Global permissions are defined in opencode.json(c)
  - Agent scoped permissions can also be defined in the frontmatter. Check inside ~/.config/opencode/agents/*.md
3. Prefer modifying existing config before creating new config.

## Rules

- Project-scoped rule overrides global-scoped rule.
- Last rule wins.

## Pitfalls

### `rtk` wrapper prefix

Most bash commands are prefixed with `rtk`. For example, command `ls /tmp/foo` becomes `rtk ls /tmp/foo`.
RTK is used to strip down excessive command outputs to reduce token usage.

When setting permission for specific command pattern, you should also add another copy for RTK.

```json
"bash": {
    "*": "deny",
    "ls": "allow",
    "rtk ls": "allow",
    "git clone *": "allow",
    "rtk git clone *": "allow",
    ...
}
```

RTK is only applied to bash tool. Built-in tools like read or grep are not affected.

### Wildcards *

Wildcard `*` is useful for writing concise permissions config, but extra care needs to be taken.
A common pattern is to deny everything first, and then gradually allow specific things. However, be aware that
basic tools like `read` and `edit` are also denied, and this could interfere with intended functionality. `external_directory` will also be denied, limiting agent to only the current workspace. `skill` will also be denied, preventing agent from loading skills. In most cases, you will want to explicitly re-allow these core tools. When uncertain, always verify with the user.

```json
// Rule to only allow reading local files
{
  "*": "deny",
  "read": {
    "*": "allow",
    // Deny .env as it can contain private keys
    "*.env": "deny",
    "*.env.*": "deny",
  },
  "grep": "allow",
  "glob": "allow",
  "skill": "allow",
  "external_directory": "allow",
  "bash": {
      "*": "deny",
      "ls": "allow",
      "find": "allow",
      "cat": "allow",
      ...
  }
}
```

### Opencode internal tools

`read`, `edit` (including `write` and `patch`), `glob` and `grep` are separate from their bash command equivalents. That means denying `grep` will not affect `bash: grep`.

## Debugging

When an agent was denied but it shouldn't have been:

1. Check the log for `action.permission=bash action.pattern=* action.action=deny`
2. Compare the **actual command string** vs your patterns.
3. If accessing files outside the workspace, verify `external_directory` covers the path with `**`.
