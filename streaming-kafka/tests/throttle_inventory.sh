#!/usr/bin/env bash
set -euo pipefail

THROTTLE_MS="${1:-50}"

echo "Setting inventory THROTTLE_MS=${THROTTLE_MS} and recreating container..."
# edit compose env by using override via docker compose run? simplest: use env var at runtime
# easiest approach: use 'docker compose up' with env override
THROTTLE_MS="$THROTTLE_MS" docker compose up -d --force-recreate inventory_consumer
echo "Done."
