---
name: create-opencode-plugin
description: "Create and edit OpenCode plugins. Covers plugin structure, events, hooks, custom tools, dependencies, and structured logging."
compatibility: opencode
---

# OpenCode Plugin Development

Create and edit OpenCode plugins. Refer to the [official plugins documentation](https://opencode.ai/docs/plugins/) for the full API reference.

## When to use

- Creating a new OpenCode plugin
- Editing an existing plugin (adding hooks, fixing logging, updating events)
- Reviewing a plugin PR or adding a plugin dependency

## Plugin locations

Plugins load from these locations (in order):

1. **Global config** — `opencode.json` plugins array in `~/.config/opencode/`
2. **Project config** — `opencode.json` plugins array in the project root
3. **Global directory** — files in `~/.config/opencode/plugins/`
4. **Project directory** — files in `.opencode/plugins/`

All hooks execute in loading order. Duplicate npm packages (same name + version) load once. See [references/hooks.md](references/hooks.md) for installation details.

## Quick skeleton

```typescript
import type { Plugin } from "@opencode-ai/plugin";

export const MyPlugin: Plugin = async ({ client, project, $, directory, worktree }) => {
  await client.app.log({
    body: {
      service: "my-plugin",
      level: "info",
      message: "Plugin initialized",
      extra: { projectId: project.id },
    },
  });

  return {
    // Hooks returned here — see references/hooks.md
  };
};
```

## Creation workflow

1. Create a `.ts` file in `.opencode/plugins/` (project) or `~/.config/opencode/plugins/` (global)
2. Export an async function matching the `Plugin` type from `@opencode-ai/plugin`
3. Add `client.app.log()` at init and in all `catch` blocks (see [references/logging.md](references/logging.md))
4. Return a hooks object (see [references/hooks.md](references/hooks.md))
5. If using npm packages, add them to `.opencode/package.json` or publish to npm with the `opencode-` prefix

## Editing existing plugins

1. **Read** the full plugin file to understand current hooks and event handlers
2. **Migrate** all `console.log` calls to `client.app.log()` (see [references/logging.md](references/logging.md))
3. **Wrap** every event handler body in `try/catch` with structured error logging
4. **Standardize** the `service` name across all log calls in the plugin
5. **Verify** the hooks object is returned and all event names match the official docs

## Key patterns

### Event handler with error logging

```typescript
import type { Plugin } from "@opencode-ai/plugin";

export const MyPlugin: Plugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        try {
          // Core plugin logic
        } catch (error) {
          await client.app.log({
            body: {
              service: "my-plugin",
              level: "error",
              message: `Failed to process session: ${(error as Error).message}`,
              extra: {
                sessionId: event.properties?.info?.id,
                stack: (error as Error).stack,
              },
            },
          });
        }
      }
    },
  };
};
```

### Custom tool

```typescript
import { type Plugin, tool } from "@opencode-ai/plugin";

export const MyPlugin: Plugin = async () => {
  return {
    tool: {
      mytool: tool({
        description: "Description of what this tool does",
        args: {
          param: tool.schema.string().describe("Parameter description"),
        },
        async execute(args, context) {
          const { sessionID, messageID, agent, abort } = context;
          return `Result: ${args.param}`;
        },
      }),
    },
  };
};
```

### Tool execution interceptor

```typescript
export const MyPlugin: Plugin = async ({ client }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "read" && output.args.filePath?.includes(".env")) {
        throw new Error("Reading .env files is not allowed");
      }
    },
    "tool.execute.after": async (input, output) => {
      if (input.tool === "edit") {
        await client.app.log({
          body: {
            service: "my-plugin",
            level: "info",
            message: `Edited ${output.args.filePath}`,
          },
        });
      }
    },
  };
};
```

## Pitfalls

- **`console.log` instead of `client.app.log()`** — logs are invisible in production. Always use structured logging.
- **Missing `body` wrapper** — SDK expects `{ body: { service, level, message, extra } }`. Omitting `body` causes silent failures.
- **No `try/catch` in event handlers** — an unhandled rejection kills the plugin. Every handler needs error handling.
- **Wrong event names** — events use dot-separated lowercase names (e.g., `session.created`, not `sessionCreated`).
- **Forgetting to return hooks** — the factory must return a hooks object. Return `{}` if no hooks yet.
- **Plugin shadows built-in tools** — a plugin tool with the same name as a built-in tool overrides it.
- **Loading order surprises** — global plugins fire before project plugins. If both handle the same event, global runs first.
- **`.mjs` imports from `.ts` are not resolved** — OpenCode's TS loader does not resolve `.mjs` imports. Use `.js` extension for all local imports within a plugin project. The import silently fails (the module evaluates without error but the imported values are undefined).
- **All `.ts`/`.js` files in `plugins/` are auto-discovered** — placing a helper module (e.g., `tokenizer-registry.js`) directly in `plugins/` causes OpenCode to attempt loading it as a plugin, producing `"Cannot call a class constructor ... without |new|"`. Move shared modules into a `lib/` subdirectory:
  ```
  plugins/
    my-plugin.ts          # entry point — exports plugin function
    lib/
      helper.ts           # imported by my-plugin.ts, not loaded as plugin
  ```
- **Plugin loads silently but tool never registers** — if the entry point imports a file that fails to evaluate (e.g., `.mjs` not resolved, or a dependency missing), the import error propagates silently and the plugin export is never recognized. Check logs for `"failed to load plugin"` with the plugin path; an error for a helper module usually means it was auto-discovered. The actual plugin file shows no error because the import chain broke before the export was exposed.

## References

- [Official plugins documentation](https://opencode.ai/docs/plugins/) — full API reference
- [SDK documentation](https://opencode.ai/docs/sdk/) — `client.app.log()` and session APIs
- [references/logging.md](references/logging.md) — structured logging patterns
- [references/hooks.md](references/hooks.md) — all hook types with examples
- [references/events.md](references/events.md) — full events list
