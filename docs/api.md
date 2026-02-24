# API Reference

The FastAPI server exposes a small API for inspecting and manually triggering integrations.

## Endpoints

### Health check

```
GET /
```

Returns a basic health check response.

### List integrations

```
GET /integrations
```

Returns all configured integrations with their type, name, and schedule.

### Trigger an integration

```
POST /integrations/{name}/run
```

Manually triggers an integration's entry task. This enqueues the same task that the scheduler would enqueue on the configured schedule. The worker picks it up and processes it like any other task.

Examples:

```bash
curl -X POST http://localhost:8000/integrations/personal/run
```

The `{name}` parameter matches the `name` field from your `config.yaml` integration entry. If you have an email integration named `personal` and a GitHub integration named `my_repos`, both are triggered by their name:

```bash
curl -X POST http://localhost:8000/integrations/personal/run
curl -X POST http://localhost:8000/integrations/my_repos/run
```

## Scheduled vs manual triggers

There is no difference in behavior. A manual `POST /integrations/{name}/run` enqueues the same entry task that the cron scheduler enqueues automatically. The worker processes both identically. Downstream task chains (collect, classify, act) are the same regardless of how the entry task was created.

Manual triggers are useful for testing your config, debugging an integration, or running a one-off check outside the normal schedule.

## Running the server

Development server with auto-reload:

```bash
uv run fastapi dev
```

Production server:

```bash
uv run fastapi run
```

The worker must run in a separate terminal for tasks to actually be processed:

```bash
uv run python -m app.worker
```
