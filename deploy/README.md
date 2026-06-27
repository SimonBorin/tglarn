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

## Local Run

From the repository root:

```bash
source ~/.zprofile
./deploy/local-up.sh
```

The helper script loads `.env` and `~/.zprofile`, validates `TG_LARN_BOT_TOKEN`, builds the bot image, starts MongoDB, and then starts the bot. If `podman-compose` is not installed, the script uses direct `podman build/run` as a fallback.

Detached mode:

```bash
source ~/.zprofile
set -a; source .env; set +a
podman compose -f deploy/compose.yml up --build -d
```

Stop containers:

```bash
./deploy/local-down.sh
```

If you used compose directly, this also works:

```bash
podman compose -f deploy/compose.yml down
```

## Planned Containers

### `tglarn-bot`

Responsibilities:

- Telegram update polling or webhook handling;
- command routing;
- game adapter execution;
- optional upstream C ReLarn pty bridge when `GAME_ADAPTER=relarn_process`;
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
TG_LARN_BOT_TOKEN=...
MONGO_INITDB_ROOT_USERNAME=tglarn
MONGO_INITDB_ROOT_PASSWORD=change-me
MONGO_DATABASE=tglarn
MONGO_URI=mongodb://tglarn:change-me@mongo:27017/tglarn?authSource=admin
DEFAULT_MAP_VIEW=wide
GAME_ADAPTER=placeholder
# GAME_ADAPTER=relarn_process enables the upstream C ReLarn pty bridge.
RELARN_BINARY_PATH=/opt/relarn/lib/relarn/relarn.bin
RELARN_INSTALL_ROOT=/opt/relarn
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
- image should build reproducibly from `Containerfile`;
- the bot image compiles upstream ReLarn during build and installs its runtime files under `/opt/relarn`.
