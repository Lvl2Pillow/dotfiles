# Hooks

Hooks are the functions a plugin returns to intercept OpenCode behavior. The plugin factory must return an object where each key is a hook name and each value is an async function.

## Installation and loading

### Local plugins

Place `.ts` or `.js` files in:
- **Project-level**: `.opencode/plugins/`
- **Global**: `~/.config/opencode/plugins/`

Local plugins are automatically loaded at startup. No config needed.

### npm plugins

Add package names to `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["opencode-helicone-session", "@my-org/custom-plugin"]
}
```

npm plugins are auto-installed via Bun on startup. Packages are cached in `~/.cache/opencode/node_modules/`.

### Local dependencies

For local plugins that need npm packages, create `.opencode/package.json`:

```json
{
  "dependencies": {
    "shescape": "^2.1.0"
  }
}
```

OpenCode runs `bun install` in the config directory at startup.

## `event` — Generic event handler

Responds to any event. Check `event.type` to branch:

```typescript
import type { Plugin } from "@opencode-ai/plugin";

export const MyPlugin: Plugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        await client.app.log({
          body: {
            service: "my-plugin",
            level: "info",
            message: "Session started",
          },
        });
      }
    },
  };
};
```

See [events.md](events.md) for all event types.

## `"tool.execute.before"` — Before tool execution

Modify or block tool arguments before execution. **Input**: `{ tool, sessionID, callID }`. **Output**: `{ args }`.

```typescript
export const MyPlugin: Plugin = async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "read" && output.args.filePath?.includes(".env")) {
        throw new Error("Reading .env files is not allowed");
      }
    },
  };
};
```

## `"tool.execute.after"` — After tool execution

Process tool results. **Output**: `{ title, output, metadata }`.

```typescript
export const MyPlugin: Plugin = async ({ $, client }) => {
  return {
    "tool.execute.after": async (input, output) => {
      if (input.tool === "edit") {
        await client.app.log({
          body: {
            service: "my-plugin",
            level: "info",
            message: "File edited",
            extra: { file: output.args.filePath },
          },
        });
        await $`prettier --write ${output.args.filePath}`;
      }
    },
  };
};
```

## `tool` — Custom tool definitions

Add tools the AI can invoke. Import `tool` from `@opencode-ai/plugin`:

```typescript
import { type Plugin, tool } from "@opencode-ai/plugin";

export const MyPlugin: Plugin = async () => {
  return {
    tool: {
      mytool: tool({
        description: "Description of the tool",
        args: {
          name: tool.schema.string().describe("Name to greet"),
          count: tool.schema.number().optional().describe("Number of times"),
        },
        async execute(args, context) {
          const { sessionID, messageID, agent, abort } = context;
          return `Hello ${args.name}!`;
        },
      }),
    },
  };
};
```

Available schema methods: `tool.schema.string()`, `.number()`, `.boolean()`, `.enum(['a', 'b'])`. Chain `.optional()`, `.default()`, `.describe()`, `.url()`.

If a plugin tool has the same name as a built-in tool, the plugin tool takes precedence.

## `"shell.env"` — Environment variable injection

Inject env vars into all shell executions (both AI and user terminal):

```typescript
export const MyPlugin: Plugin = async () => {
  return {
    "shell.env": async (input, output) => {
      // input: { cwd }
      // output: { env } — mutable, add properties
      output.env.MY_API_KEY = "secret";
      output.env.PROJECT_ROOT = input.cwd;
    },
  };
};
```

## `"experimental.session.compacting"` — Custom compaction context

Inject domain-specific context during session compaction:

```typescript
export const MyPlugin: Plugin = async () => {
  return {
    "experimental.session.compacting": async (input, output) => {
      output.context.push(`## Custom Context\n- Current task: ...`);

      // To fully replace the compaction prompt instead:
      // output.prompt = "Custom compaction instructions...";
    },
  };
};
```

When `output.prompt` is set, `output.context` is ignored and the prompt fully replaces the default.

## `"permission.ask"` — Auto-allow/deny permissions

Programmatically respond to permission requests:

```typescript
export const MyPlugin: Plugin = async () => {
  return {
    "permission.ask": async (permission, output) => {
      if (permission.type === "read_file" && permission.path.endsWith(".env")) {
        output.status = "deny";
      }
    },
  };
};
```

## `"chat.message"` — Intercept chat messages

Modify messages before they reach the LLM:

```typescript
export const MyPlugin: Plugin = async () => {
  return {
    "chat.message": async (input, output) => {
      // input: { message, parts }
      // output: { message, parts }
    },
  };
};
```

## `"chat.params"` — Modify LLM parameters

Adjust temperature, topP, or add custom options:

```typescript
export const MyPlugin: Plugin = async () => {
  return {
    "chat.params": async (input, output) => {
      // input: { model, provider, message }
      // output: { temperature, topP, options }
      output.temperature = 0.7;
    },
  };
};
```

## `auth` — Authentication providers

Add custom auth methods for external services:

```typescript
export const MyPlugin: Plugin = async () => {
  return {
    auth: {
      provider: "myservice",
      methods: [
        {
          type: "api",
          label: "API Key",
        },
      ],
    },
  };
};
```

Supported method types: `api`, `oauth`, `bearer`.

## `config` — Configuration hook

Modify OpenCode configuration at startup:

```typescript
export const MyPlugin: Plugin = async () => {
  return {
    config: async (config) => {
      config.myPlugin = { enabled: true };
    },
  };
};
```
