#!/usr/bin/env bash
set -Eeuo pipefail

readonly PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

exec bash "$PROJECT_DIR/scripts/deploy.sh" "$@"
