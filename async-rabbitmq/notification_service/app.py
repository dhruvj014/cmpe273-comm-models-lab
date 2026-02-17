"""
NotificationService — Consumes InventoryReserved events and simulates sending
email/SMS confirmations to students.
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
logger = logging.getLogger("NotificationService")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
EXCHANGE = "order_events"

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
    """Declare exchange and queues used by NotificationService."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue="notification_queue", durable=True)
    channel.queue_bind(queue="notification_queue", exchange=EXCHANGE, routing_key="inventory.reserved")


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------

def on_inventory_reserved(ch, method, properties, body):
    """Handle InventoryReserved event — simulate sending notification."""
    try:
        data = json.loads(body)
        order_id = data.get("order_id", "UNKNOWN")
        item = data.get("item", "UNKNOWN")
        qty = data.get("qty", 0)
        student_id = data.get("student_id", "UNKNOWN")

        logger.info(
            "[NOTIFICATION] Order %s confirmed — sending email/SMS to %s (%s x%d)",
            order_id, student_id, item, qty,
        )
        # Simulate notification delay
        time.sleep(0.5)
        logger.info("[NOTIFICATION] Confirmation sent for order %s", order_id)

    except Exception as e:
        logger.error("Error processing notification: %s", e)
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------

def main():
    """Connect to RabbitMQ and consume InventoryReserved events."""
    while True:
        try:
            conn = get_connection()
            ch = conn.channel()
            setup_channel(ch)
            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(
                queue="notification_queue",
                on_message_callback=on_inventory_reserved,
                auto_ack=False,
            )
            logger.info("NotificationService ready — waiting for InventoryReserved events...")
            ch.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            logger.warning("Lost connection to RabbitMQ, reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            logger.error("Unexpected error: %s, restarting in 5s...", e)
            time.sleep(5)


def graceful_shutdown(signum, frame):
    logger.info("Shutting down NotificationService...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    main()
