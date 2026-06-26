# Deployment

## Deployment Principle

`tglarn` should run as containers, not as manually installed services on the VM.

MVP target:

- Podman on a single VM.
- Bot container.
- MongoDB container.
- Named volumes for database data.
- Runtime configuration through environment variables or mounted secret files.

Future target:

- Kubernetes-compatible manifests or Helm chart.
- Separate managed database is allowed, but the bot runtime itself remains containerized.
- The application should not depend on local paths outside mounted volumes.

## Planned Containers

### `tglarn-bot`

Responsibilities:

- Telegram update polling or webhook handling;
- command routing;
- game adapter execution;
- database connection through `MONGO_URI`.

### `mongo`

MVP persistence container.

Responsibilities:

- player metadata;
- direct chat metadata;
- game session state;
- turn history.

In future AWS deployment, this may be replaced by Amazon DocumentDB. The bot should only need a different `MONGO_URI` and TLS configuration.

## Configuration

No secrets should be committed. Expected runtime configuration:

```text
BOT_TOKEN=...
MONGO_URI=mongodb://tglarn_user:password@mongo:27017/tglarn?authSource=admin&retryWrites=false
MONGO_DB=tglarn
```

## Kubernetes Readiness Notes

Keep these constraints in mind while implementing:

- one process per container;
- logs to stdout/stderr;
- graceful shutdown on SIGTERM;
- health/readiness endpoints or lightweight health commands;
- configuration from environment variables;
- no local mutable state except mounted volumes;
- database migrations/index creation should be repeatable and safe;
- image should build reproducibly from `Containerfile`.
