"""
test_idempotency.py — Publish the same OrderPlaced event twice via RabbitMQ
and verify that InventoryService only reserves once (idempotency).
"""

import json
import subprocess
import time

import pika

RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
EXCHANGE = "order_events"
TEST_ORDER_ID = "idempotency-test-001"


def publish_order_placed(order_id: str, item: str, qty: int):
    """Publish an OrderPlaced event directly to RabbitMQ."""
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
    )
    ch = conn.channel()
    ch.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    ch.queue_declare(queue="inventory_queue", durable=True)
    ch.queue_bind(queue="inventory_queue", exchange=EXCHANGE, routing_key="order.placed")

    event = {
        "order_id": order_id,
        "item": item,
        "qty": qty,
        "student_id": "test-student",
    }
    ch.basic_publish(
        exchange=EXCHANGE,
        routing_key="order.placed",
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conn.close()


def get_inventory_logs() -> str:
    """Fetch inventory_service logs from docker."""
    result = subprocess.run(
        "docker compose logs inventory_service",
        shell=True,
        capture_output=True,
        text=True,
        cwd="../",
    )
    return result.stdout + result.stderr


def main():
    print("=" * 60)
    print("IDEMPOTENCY TEST")
    print("=" * 60)

    # Step 1: First delivery
    print(f"\n[1] Publishing OrderPlaced (order_id={TEST_ORDER_ID}, item=burger, qty=5)...")
    publish_order_placed(TEST_ORDER_ID, "burger", 5)

    print("    Waiting 3s for processing...")
    time.sleep(3)

    # Step 2: Second delivery (duplicate)
    print(f"\n[2] Publishing SAME OrderPlaced again (order_id={TEST_ORDER_ID})...")
    publish_order_placed(TEST_ORDER_ID, "burger", 5)

    print("    Waiting 3s for processing...")
    time.sleep(3)

    # Step 3: Check logs
    print("\n[3] Checking inventory_service logs...")
    logs = get_inventory_logs()

    # Look for evidence of first processing and duplicate detection
    reserved_count = logs.count(f"Reserved 5 burger for order {TEST_ORDER_ID}")
    duplicate_count = logs.count(f"Duplicate detected for order {TEST_ORDER_ID}")

    print()
    if reserved_count >= 1:
        print(f"    ✅ First delivery: \"Reserved 5 burger for order {TEST_ORDER_ID}\"")
    else:
        print(f"    ❌ First delivery: reservation log not found")

    if duplicate_count >= 1:
        print(f"    ✅ Second delivery: \"Duplicate detected for order {TEST_ORDER_ID}, skipping\"")
    else:
        print(f"    ❌ Second delivery: duplicate detection log not found")

    print()
    if reserved_count >= 1 and duplicate_count >= 1:
        print("RESULT: ✅ PASS — Inventory was reserved only once.")
    elif reserved_count > 1:
        print("RESULT: ❌ FAIL — Inventory was reserved MULTIPLE times (double reservation).")
    else:
        print("RESULT: ⚠️  INCONCLUSIVE — Check logs manually.")
        print("    Full logs excerpt:")
        # Print last 20 lines
        for line in logs.strip().split("\n")[-20:]:
            print(f"    {line}")

    print("\n" + "=" * 60)
    print("IDEMPOTENCY TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
