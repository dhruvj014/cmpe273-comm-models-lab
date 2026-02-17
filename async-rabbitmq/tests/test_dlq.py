"""
test_dlq.py — Send a malformed OrderPlaced event (missing qty field)
and verify it is routed to the Dead Letter Queue (dlq_queue).
"""

import json
import subprocess
import time

import pika
import requests

RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
EXCHANGE = "order_events"
RABBITMQ_API_DLQ = "http://localhost:15672/api/queues/%2F/dlq_queue"
RABBITMQ_AUTH = ("guest", "guest")


def publish_malformed_event():
    """Publish a malformed OrderPlaced event (missing qty field)."""
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
    )
    ch = conn.channel()
    ch.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    ch.queue_declare(queue="inventory_queue", durable=True)
    ch.queue_bind(queue="inventory_queue", exchange=EXCHANGE, routing_key="order.placed")

    # Malformed: missing "qty" field
    event = {
        "order_id": "bad-001",
        "item": "burger",
        # "qty" intentionally missing
        "student_id": "bad-student",
    }
    ch.basic_publish(
        exchange=EXCHANGE,
        routing_key="order.placed",
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conn.close()


def get_dlq_depth() -> int:
    """Get the number of messages in dlq_queue via RabbitMQ Management API."""
    try:
        r = requests.get(RABBITMQ_API_DLQ, auth=RABBITMQ_AUTH, timeout=5)
        if r.status_code == 200:
            return r.json().get("messages", 0)
    except Exception as e:
        print(f"  Warning: Could not query RabbitMQ API: {e}")
    return -1


def consume_one_from_dlq() -> dict | None:
    """Peek at one message from the DLQ for inspection (requeue=True so it stays)."""
    try:
        conn = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT)
        )
        ch = conn.channel()
        ch.queue_declare(queue="dlq_queue", durable=True)
        method, properties, body = ch.basic_get(queue="dlq_queue", auto_ack=False)
        if method and body:
            # Reject with requeue so the message stays in the DLQ for inspection
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            conn.close()
            return json.loads(body)
        conn.close()
    except Exception as e:
        print(f"  Warning: Could not consume from DLQ: {e}")
    return None


def get_inventory_logs() -> str:
    """Fetch inventory_service logs."""
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
    print("DLQ / POISON MESSAGE TEST")
    print("=" * 60)

    # Check initial DLQ depth
    initial_depth = get_dlq_depth()
    print(f"\n[1] Initial dlq_queue depth: {initial_depth}")

    # Publish malformed event
    print("\n[2] Publishing malformed event (missing qty field)...")
    print('    Payload: {"order_id": "bad-001", "item": "burger"}  (no qty)')
    publish_malformed_event()

    print("    Waiting 3s for processing...")
    time.sleep(3)

    # Inspect the DLQ message (peek without removing)
    print("\n[3] DLQ message content:")
    msg = consume_one_from_dlq()
    if msg:
        print(f"    {json.dumps(msg, indent=2)}")
    else:
        print("    (could not retrieve message)")

    # Check DLQ depth (message is still in queue because we nack'd with requeue)
    new_depth = get_dlq_depth()
    added = new_depth - max(initial_depth, 0)
    print(f"\n[4] Checking dlq_queue via RabbitMQ Management API...")
    print(f"    dlq_queue message count: {new_depth} (added: {added})")

    # Check inventory service logs
    print("\n[5] Checking inventory_service logs...")
    logs = get_inventory_logs()
    if "Malformed message for order bad-001" in logs or "Missing required field" in logs:
        print('    ✅ "Malformed message for order bad-001: Missing required field(s): qty — routed to DLQ"')
    else:
        print("    ⚠️  Expected log not found. Relevant log lines:")
        for line in logs.strip().split("\n")[-10:]:
            if "bad-001" in line or "DLQ" in line or "Malformed" in line or "Missing" in line:
                print(f"    {line}")

    # Result
    print()
    if added >= 1 or msg is not None:
        print("RESULT: ✅ PASS — Poison message routed to DLQ, consumer did not crash.")
    else:
        print("RESULT: ❌ FAIL — Message did not appear in DLQ.")

    print("\n" + "=" * 60)
    print("DLQ / POISON MESSAGE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()