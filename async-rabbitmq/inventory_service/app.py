"""
InventoryService — Consumes OrderPlaced events from RabbitMQ, reserves inventory,
publishes InventoryReserved or InventoryFailed. Handles idempotency and malformed messages.
"""

import json
import logging
import os
import signal
import sys
import time

import pika

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("InventoryService")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
EXCHANGE = "order_events"

# ---------------------------------------------------------------------------
# In-memory inventory and idempotency tracking
# ---------------------------------------------------------------------------
inventory = {
    "burger": 100,
    "pizza": 50,
    "sushi": 30,
    "salad": 200,
}

# Idempotency: track already-processed order IDs to prevent double reservations
processed_orders: set = set()

# ---------------------------------------------------------------------------
# RabbitMQ helpers
# ---------------------------------------------------------------------------

def get_connection(retries: int = 15, delay: int = 5) -> pika.BlockingConnection:
    """Create a blocking connection to RabbitMQ with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            conn = pika.BlockingConnection(params)
            logger.info("Connected to RabbitMQ (attempt %d)", attempt)
            return conn
        except pika.exceptions.AMQPConnectionError:
            logger.warning("RabbitMQ not ready, retrying in %ds (%d/%d)", delay, attempt, retries)
            time.sleep(delay)
    logger.error("Could not connect to RabbitMQ after %d attempts", retries)
    sys.exit(1)


def setup_channel(channel):
    """Declare exchange and queues used by InventoryService."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue="inventory_queue", durable=True)
    channel.queue_bind(queue="inventory_queue", exchange=EXCHANGE, routing_key="order.placed")
    channel.queue_declare(queue="dlq_queue", durable=True)


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

def on_order_placed(ch, method, properties, body):
    """
    Handle an incoming OrderPlaced message.
    1. Validate required fields (order_id, item, qty).
    2. Check idempotency — skip if already processed.
    3. Check stock and reserve or fail.
    4. Publish result event.
    """
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Could not decode message body, routing to DLQ")
        ch.basic_publish(
            exchange="",
            routing_key="dlq_queue",
            body=body,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    order_id = data.get("order_id")
    item = data.get("item")
    qty = data.get("qty")

    # --- Validation: check required fields ---
    missing = []
    if not order_id:
        missing.append("order_id")
    if not item:
        missing.append("item")
    if qty is None:
        missing.append("qty")

    if missing:
        reason = f"Missing required field(s): {', '.join(missing)}"
        logger.warning("Malformed message for order %s: %s — routed to DLQ", order_id or "UNKNOWN", reason)
        dlq_msg = {**data, "error": reason}
        ch.basic_publish(
            exchange="",
            routing_key="dlq_queue",
            body=json.dumps(dlq_msg),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # Validate qty is a positive integer
    if not isinstance(qty, int) or qty <= 0:
        reason = f"Invalid qty: {qty} (must be a positive integer)"
        logger.warning("Malformed message for order %s: %s — routed to DLQ", order_id, reason)
        dlq_msg = {**data, "error": reason}
        ch.basic_publish(
            exchange="",
            routing_key="dlq_queue",
            body=json.dumps(dlq_msg),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # --- Idempotency check ---
    if order_id in processed_orders:
        logger.info("Duplicate detected for order %s, skipping", order_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # --- Stock check and reservation ---
    if item not in inventory:
        reason = f"Item '{item}' not found in inventory"
        logger.warning("InventoryFailed for order %s: %s", order_id, reason)
        event = {
            "order_id": order_id,
            "item": item,
            "qty": qty,
            "status": "FAILED",
            "reason": reason,
        }
        ch.basic_publish(
            exchange=EXCHANGE,
            routing_key="inventory.failed",
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    if inventory[item] < qty:
        reason = f"Insufficient stock for '{item}': requested {qty}, available {inventory[item]}"
        logger.warning("InventoryFailed for order %s: %s", order_id, reason)
        event = {
            "order_id": order_id,
            "item": item,
            "qty": qty,
            "status": "FAILED",
            "reason": reason,
        }
        ch.basic_publish(
            exchange=EXCHANGE,
            routing_key="inventory.failed",
            body=json.dumps(event),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # Reserve stock
    inventory[item] -= qty
    processed_orders.add(order_id)

    logger.info(
        "Reserved %d %s for order %s (remaining: %d)",
        qty, item, order_id, inventory[item],
    )

    event = {
        "order_id": order_id,
        "item": item,
        "qty": qty,
        "status": "RESERVED",
    }
    ch.basic_publish(
        exchange=EXCHANGE,
        routing_key="inventory.reserved",
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    ch.basic_ack(delivery_tag=method.delivery_tag)


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------

def main():
    """Connect to RabbitMQ and consume OrderPlaced events."""
    while True:
        try:
            conn = get_connection()
            ch = conn.channel()
            setup_channel(ch)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue="inventory_queue", on_message_callback=on_order_placed, auto_ack=False)
            logger.info("InventoryService ready — waiting for OrderPlaced events...")
            logger.info("Current inventory: %s", inventory)
            ch.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            logger.warning("Lost connection to RabbitMQ, reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            logger.error("Unexpected error: %s, restarting in 5s...", e)
            time.sleep(5)


def graceful_shutdown(signum, frame):
    logger.info("Shutting down InventoryService...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    main()
