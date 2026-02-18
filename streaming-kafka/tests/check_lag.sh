#!/usr/bin/env bash
set -euo pipefail

GROUP="${1:-inventory-service}"
BOOTSTRAP="kafka:29092"

echo "Checking lag for group=$GROUP (Ctrl+C to stop)"
while true; do
  docker compose exec -T kafka bash -lc \
    "kafka-consumer-groups --bootstrap-server $BOOTSTRAP --describe --group $GROUP | sed -n '1,5p'"
  echo "----"
  sleep 2
done
