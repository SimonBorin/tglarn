#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Review it if you need custom local Mongo credentials."
fi

set -a
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi
if [[ -f "$HOME/.zprofile" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.zprofile"
fi
set +a

if [[ -z "${TG_LARN_BOT_TOKEN:-}" ]]; then
  echo "TG_LARN_BOT_TOKEN is required. Put it in .env or export it from ~/.zprofile." >&2
  exit 1
fi

if command -v podman-compose >/dev/null 2>&1; then
  exec podman-compose -f deploy/compose.yml up --build "$@"
fi

if [[ "${TGLARN_USE_PODMAN_COMPOSE:-0}" == "1" ]]; then
  exec podman compose -f deploy/compose.yml up --build "$@"
fi

echo "podman-compose is not installed; using direct podman fallback."

DETACH=0
for arg in "$@"; do
  case "$arg" in
    -d|--detach)
      DETACH=1
      ;;
  esac
done

MONGO_USER="${MONGO_INITDB_ROOT_USERNAME:-tglarn}"
MONGO_PASSWORD="${MONGO_INITDB_ROOT_PASSWORD:-change-me}"
MONGO_DB="${MONGO_DATABASE:-tglarn}"
CONTAINER_MONGO_URI="mongodb://${MONGO_USER}:${MONGO_PASSWORD}@tglarn-mongo:27017/${MONGO_DB}?authSource=admin"

podman network exists tglarn >/dev/null 2>&1 || podman network create tglarn >/dev/null
podman volume exists tglarn-mongo-data >/dev/null 2>&1 || podman volume create tglarn-mongo-data >/dev/null

podman build -f Containerfile -t localhost/tglarn-bot:dev .

podman rm -f tglarn-bot >/dev/null 2>&1 || true
podman rm -f tglarn-mongo >/dev/null 2>&1 || true

podman run -d   --name tglarn-mongo   --network tglarn   -p 127.0.0.1:27017:27017   -v tglarn-mongo-data:/data/db   -e MONGO_INITDB_ROOT_USERNAME="$MONGO_USER"   -e MONGO_INITDB_ROOT_PASSWORD="$MONGO_PASSWORD"   -e MONGO_INITDB_DATABASE="$MONGO_DB"   docker.io/library/mongo:7 >/dev/null

BOT_ARGS=(
  --name tglarn-bot
  --network tglarn
  -e "TG_LARN_BOT_TOKEN=${TG_LARN_BOT_TOKEN}"
  -e "MONGO_DATABASE=${MONGO_DB}"
  -e "MONGO_URI=${CONTAINER_MONGO_URI}"
  -e "DEFAULT_MAP_VIEW=${DEFAULT_MAP_VIEW:-wide}"
  -e "GAME_ADAPTER=${GAME_ADAPTER:-placeholder}"
  -e "RELARN_BINARY_PATH=${RELARN_BINARY_PATH:-/opt/relarn/lib/relarn/relarn.bin}"
  -e "RELARN_INSTALL_ROOT=${RELARN_INSTALL_ROOT:-/opt/relarn}"
  -e "RELARN_CYCLE_TIMEOUT_SECONDS=${RELARN_CYCLE_TIMEOUT_SECONDS:-3}"
  -e "RELARN_CYCLE_SETTLE_SECONDS=${RELARN_CYCLE_SETTLE_SECONDS:-0.12}"
  -e "REPOSITORY_URL=${REPOSITORY_URL:-https://github.com/SimonBorin/tglarn}"
  -e "LOG_LEVEL=${LOG_LEVEL:-INFO}"
  -e "DATABASE_STARTUP_ATTEMPTS=${DATABASE_STARTUP_ATTEMPTS:-30}"
  -e "DATABASE_STARTUP_DELAY_SECONDS=${DATABASE_STARTUP_DELAY_SECONDS:-2}"
)

if [[ "$DETACH" == "1" ]]; then
  podman run -d "${BOT_ARGS[@]}" localhost/tglarn-bot:dev >/dev/null
  echo "Started tglarn-bot and tglarn-mongo."
  echo "Logs: podman logs -f tglarn-bot"
else
  exec podman run --rm "${BOT_ARGS[@]}" localhost/tglarn-bot:dev
fi
