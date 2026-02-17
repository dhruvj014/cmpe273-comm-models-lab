#!/bin/bash
set -e

echo "============================================================"
echo " PART B: ASYNC RABBITMQ — ALL TESTS"
echo "============================================================"
echo ""

echo "========== BACKLOG DRAIN TEST =========="
python3 test_backlog_drain.py
echo ""

echo "========== IDEMPOTENCY TEST =========="
python3 test_idempotency.py
echo ""

echo "========== DLQ / POISON MESSAGE TEST =========="
python3 test_dlq.py
echo ""

echo "============================================================"
echo " ALL TESTS COMPLETED"
echo "============================================================"
