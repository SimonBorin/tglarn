#!/usr/bin/env bash
set -euo pipefail

podman rm -f tglarn-bot >/dev/null 2>&1 || true
podman rm -f tglarn-mongo >/dev/null 2>&1 || true

echo "Stopped tglarn local containers. Mongo data volume is preserved: tglarn-mongo-data"
