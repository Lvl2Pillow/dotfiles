# Structured Logging

Always use `client.app.log()` instead of `console.log`. Structured logging integrates with OpenCode's log system, making entries visible in the UI and filterable by service, level, and time.

## Canonical form

```typescript
await client.app.log({
  body: {
    service: "my-plugin",  // Identifies your plugin in log filters
    level: "info",          // debug | info | warn | error
    message: "Human-readable description of what happened",
    extra: { ... },         // Optional structured metadata (must be an object)
  },
});
```

**Important**: The `body` wrapper is required by the SDK API. Omitting it is the most common logging mistake — the log entry is silently dropped.

## Log levels

| Level   | When to use                              |
|---------|------------------------------------------|
| `debug` | Detailed info for troubleshooting        |
| `info`  | Normal operation events (init, success)  |
| `warn`  | Unexpected but non-fatal situations      |
| `error` | Failures and exceptions                  |

## Patterns

### Plugin initialization

Log when the plugin loads so operators can confirm it is active:

```typescript
export const MyPlugin: Plugin = async ({ client, project }) => {
  await client.app.log({
    body: {
      service: "my-plugin",
      level: "info",
      message: "Plugin initialized",
      extra: { projectId: project.id },
    },
  });

  return { ... };
};
```

### Error handling in event handlers

Every event handler that can throw must be wrapped in `try/catch`:

```typescript
export const MyPlugin: Plugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        try {
          // Plugin logic that could throw
        } catch (error) {
          await client.app.log({
            body: {
              service: "my-plugin",
              level: "error",
              message: `Failed to process session: ${(error as Error).message}`,
              extra: {
                sessionId: event.properties?.info?.id,
                eventType: event.type,
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

### Debug logging in tool interceptors

Use `level: "debug"` for verbose information that should not normally be visible:

```typescript
export const MyPlugin: Plugin = async ({ client }) => {
  return {
    "tool.execute.before": async (input, output) => {
      await client.app.log({
        body: {
          service: "my-plugin",
          level: "debug",
          message: `Tool ${input.tool} executing`,
          extra: { sessionID: input.sessionID, args: output.args },
        },
      });
    },
  };
};
```

## Common mistakes

| Mistake | Correct |
|---------|---------|
| `console.log("init")` | `client.app.log({ body: { service: "my-plugin", level: "info", message: "init" } })` |
| `client.app.log({ service: "...", ... })` (no `body`) | `client.app.log({ body: { service: "...", ... } })` |
| Plugin logic without `try/catch` around it | Wrap logic in `try` and log errors in `catch` |
| `extra` set to a string or number | `extra` must be a plain object |
| Inconsistent `service` name across log calls | Use the same `service` string everywhere in one plugin |
| Forgetting `await` on `client.app.log()` | Always await — fire-and-forget can silently lose entries |
