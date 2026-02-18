#!/usr/bin/env bash
set -euo pipefail

GROUP="${1:-analytics-service}"
BOOTSTRAP="kafka:29092"

echo "Resetting offsets for group=$GROUP to earliest on all topics..."
docker compose exec -T kafka bash -lc \
  "kafka-consumer-groups --bootstrap-server $BOOTSTRAP --group $GROUP --reset-offsets --to-earliest --execute --all-topics"
echo "Done."
