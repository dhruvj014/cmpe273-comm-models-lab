# Part B: Async Messaging with RabbitMQ

## Architecture

```
┌──────────────┐     ┌───────────────────────────────────────┐
│   Client     │     │            RabbitMQ Broker             │
│  (curl/test) │     │                                       │
└──────┬───────┘     │  Exchange: order_events (topic)       │
       │             │                                       │
       │ POST /order │  ┌─────────────────┐                  │
       ▼             │  │ inventory_queue  │──order.placed──┐ │
┌──────────────┐     │  └─────────────────┘                │ │
│ OrderService │────▶│  ┌──────────────────┐               │ │
│  (Flask)     │     │  │order_status_queue│◀─inv.reserved │ │
│  port 5001   │◀────│  │                  │◀─inv.failed   │ │
└──────────────┘     │  └──────────────────┘               │ │
                     │  ┌───────────────────┐              │ │
                     │  │notification_queue │◀─inv.reserved│ │
                     │  └─────────┬─────────┘              │ │
                     │  ┌─────────┐                        │ │
                     │  │dlq_queue│ (poison messages)      │ │
                     │  └─────────┘                        │ │
                     └──────────┼──────────────────────────┼─┘
                                │                          │
                                ▼                          ▼
                     ┌───────────────────┐    ┌─────────────────────┐
                     │NotificationService│    │  InventoryService   │
                     │   (consumer)      │    │    (consumer)       │
                     └───────────────────┘    │  - idempotency set  │
                                              │  - DLQ routing      │
                                              └─────────────────────┘
```

## Event Flow

1. **Client** → `POST /order` → **OrderService**
2. **OrderService** publishes `OrderPlaced` → `order.placed`
3. **InventoryService** consumes `OrderPlaced`:
   - Validates message fields
   - Checks idempotency (skip duplicates)
   - Reserves stock → publishes `InventoryReserved` (`inventory.reserved`)
   - Or fails → publishes `InventoryFailed` (`inventory.failed`)
   - Malformed → routes to `dlq_queue`
4. **NotificationService** consumes `InventoryReserved` → sends confirmation
5. **OrderService** background thread consumes status events → updates order status

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for test scripts)
- `pip install requests pika`

## Build & Run

```bash
cd async-rabbitmq
docker compose up --build -d
```

Wait ~15s for RabbitMQ to initialize, then verify:

```bash
docker compose ps                    # all containers should be Up
docker compose logs -f               # watch live logs
```

**RabbitMQ Dashboard**: http://localhost:15672 (guest / guest)

## Quick Smoke Test

```bash
# Place an order
curl -X POST http://localhost:5001/order \
  -H "Content-Type: application/json" \
  -d '{"item": "burger", "qty": 2, "student_id": "s123"}'

# Check order status
curl http://localhost:5001/order/<order_id>

# List all orders
curl http://localhost:5001/orders
```

## Run Tests

```bash
cd tests

# Individual tests
python3 test_backlog_drain.py
python3 test_idempotency.py
python3 test_dlq.py

# Or all at once
bash run_all_tests.sh
```

## Test Descriptions & Expected Outputs

### Test 1: Backlog Drain
Stops InventoryService, publishes 20 orders, restarts, and shows the queue draining to 0.

**Why it works**: RabbitMQ persists messages in durable queues. While InventoryService is down, messages accumulate. On restart, the consumer processes the backlog. This demonstrates the decoupling benefit of async messaging.

### Test 2: Idempotency
Publishes the same OrderPlaced event twice (same order_id). The first is processed normally; the second is detected as a duplicate and skipped.

**Strategy**: InventoryService maintains an in-memory `processed_orders` set. Before reserving, it checks if the order_id exists in the set. If so, it acks without side effects. In production, this would use a database or Redis for durability.

### Test 3: DLQ (Dead Letter Queue)
Publishes a malformed event (missing `qty` field). InventoryService validates the message, rejects it, and routes it to `dlq_queue`.

**Why it matters**: Without DLQ handling, a poison message would either crash the consumer or requeue infinitely. The DLQ pattern isolates bad messages for later inspection.

## Teardown

```bash
docker compose down -v
```
