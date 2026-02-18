#!/usr/bin/env bash
set -euo pipefail

echo "1) Build and start stack"
docker compose up -d --build

echo "2) Produce 10k events"
docker compose exec -T producer_order python produce_10k.py

echo "3) Show analytics report"
docker compose exec -T analytics_consumer cat /app/metrics_report.json | head -n 40

echo "4) Reset analytics offsets and restart analytics"
./tests/reset_offsets.sh analytics-service
docker compose restart analytics_consumer
sleep 5

echo "5) Show analytics report after replay"
docker compose exec -T analytics_consumer cat /app/metrics_report.json | head -n 40

echo "Done."
