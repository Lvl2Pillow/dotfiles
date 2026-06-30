# Events

All available events for OpenCode plugins. Subscribe to these via the `event` hook (see [hooks.md](hooks.md)).

## Session events

- `session.created` — a new session started
- `session.updated` — session properties changed
- `session.deleted` — a session was removed
- `session.error` — a session encountered an error
- `session.idle` — a session became idle
- `session.compacted` — session was compacted
- `session.diff` — session diff generated
- `session.status` — session status changed

## File events

- `file.edited` — a file was edited
- `file.watcher.updated` — file watcher detected changes (add/change/unlink)

## Message events

- `message.updated` — a message was updated
- `message.removed` — a message was removed
- `message.part.updated` — a message part was updated
- `message.part.removed` — a message part was removed

## Permission events

- `permission.asked` — a permission request was created
- `permission.replied` — a permission request received a response

## LSP events

- `lsp.client.diagnostics` — LSP diagnostics received
- `lsp.updated` — LSP data was updated

## Tool events

- `tool.execute.before` — fires before a tool executes (see [hooks.md](hooks.md) for interceptor API)
- `tool.execute.after` — fires after a tool executes

## Shell events

- `shell.env` — fires to populate environment variables for shell commands

## TUI events

- `tui.prompt.append` — text was appended to the TUI prompt
- `tui.command.execute` — a command was executed in the TUI
- `tui.toast.show` — a toast notification was shown

## Other events

- `command.executed` — a command was executed
- `installation.updated` — installation was updated
- `server.connected` — server connection established
- `todo.updated` — a todo item was updated
