# API Reference

The FastAPI server exposes a small API for inspecting and manually triggering integrations.

## Endpoints

### Health check

```
GET /
```

Returns `{"status": "ok"}`.

### List integrations

```
GET /integrations
```

Returns all configured integrations with their composite ID, type, name, and enabled platforms.

### Trigger an integration

```
POST /integrations/{integration_id}/run
POST /integrations/{integration_id}/{platform}/run
```

Enqueues entry tasks for an integration. The first form fires all enabled platforms. The second targets a specific one.

The `{integration_id}` is a composite ID in `{type}.{name}` format, like `email.personal` or `github.my_repos`. You can grab these from `GET /integrations`.

```bash
# Fire all platforms for the personal email integration
curl -X POST http://localhost:6767/integrations/email.personal/run

# Just the GitHub issues platform
curl -X POST http://localhost:6767/integrations/github.my_repos/issues/run
```

## Scheduled vs manual triggers

No difference in behavior. A manual POST enqueues the same entry tasks that the cron scheduler would. The worker processes both identically, and the downstream task chain (collect, classify, evaluate, act) is the same either way.

Useful for having an external trigger, testing your config, or debugging an integration outside the normal schedule.

## Running the server

The easiest way is the supervisor, which starts both the API server and the worker in one terminal:

```bash
uv run python -m app.supervisor --dev
```

The server binds to `127.0.0.1:6767` by default. If you want to hit the API from another machine on your network (a phone, a Raspberry Pi, whatever), add `--expose`:

```bash
uv run python -m app.supervisor --dev --expose
```

That binds to `0.0.0.0` instead. You can also change the port:

```bash
uv run python -m app.supervisor --port 8080
```

Or run the server and worker separately if you prefer:

```bash
uv run fastapi dev             # Dev server (auto-reload)
uv run python -m app.worker    # Task worker (separate terminal)
```

Note: `--expose` and `--port` are supervisor flags. When running `fastapi dev` directly, pass `--host` and `--port` to uvicorn yourself.
