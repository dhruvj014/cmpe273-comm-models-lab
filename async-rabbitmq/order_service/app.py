"""
OrderService — Accepts orders via REST, publishes OrderPlaced events to RabbitMQ,
and listens for inventory status updates in a background thread.
"""

import json
import logging
import os
import signal
import sys
import threading
import time
import uuid

import pika
from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("OrderService")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
EXCHANGE = "order_events"

# ---------------------------------------------------------------------------
# In-memory order store
# ---------------------------------------------------------------------------
orders: dict = {}
orders_lock = threading.Lock()

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


def setup_channel(channel: pika.adapters.blocking_connection.BlockingChannel):
    """Declare exchange and queues used by OrderService."""
    # Topic exchange
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)

    # Queue for order service to receive status updates
    channel.queue_declare(queue="order_status_queue", durable=True)
    channel.queue_bind(queue="order_status_queue", exchange=EXCHANGE, routing_key="inventory.reserved")
    channel.queue_bind(queue="order_status_queue", exchange=EXCHANGE, routing_key="inventory.failed")

    # Also declare the queues other services use (idempotent)
    channel.queue_declare(queue="inventory_queue", durable=True)
    channel.queue_bind(queue="inventory_queue", exchange=EXCHANGE, routing_key="order.placed")

    channel.queue_declare(queue="notification_queue", durable=True)
    channel.queue_bind(queue="notification_queue", exchange=EXCHANGE, routing_key="inventory.reserved")

    # Dead-letter queue
    channel.queue_declare(queue="dlq_queue", durable=True)


# ---------------------------------------------------------------------------
# Background consumer — listens for inventory status updates
# ---------------------------------------------------------------------------

def status_consumer():
    """Background thread that updates order statuses from inventory events."""
    while True:
        try:
            conn = get_connection()
            ch = conn.channel()
            setup_channel(ch)
            ch.basic_qos(prefetch_count=1)

            def on_status(ch, method, properties, body):
                try:
                    data = json.loads(body)
                    order_id = data.get("order_id")
                    status = data.get("status", "UNKNOWN")
                    new_status = "CONFIRMED" if status == "RESERVED" else "FAILED"
                    with orders_lock:
                        if order_id in orders:
                            orders[order_id]["status"] = new_status
                            logger.info("Order %s updated to %s", order_id, new_status)
                        else:
                            logger.warning("Status update for unknown order %s", order_id)
                except Exception as e:
                    logger.error("Error processing status update: %s", e)
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            ch.basic_consume(queue="order_status_queue", on_message_callback=on_status, auto_ack=False)
            logger.info("Status consumer started, waiting for inventory events...")
            ch.start_consuming()
        except pika.exceptions.AMQPConnectionError:
            logger.warning("Status consumer lost connection, reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            logger.error("Status consumer error: %s, restarting in 5s...", e)
            time.sleep(5)


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)


@app.route("/order", methods=["POST"])
def place_order():
    """Place a new order and publish OrderPlaced event."""
    data = request.get_json(force=True)
    item = data.get("item")
    qty = data.get("qty")
    student_id = data.get("student_id", "unknown")

    if not item or qty is None:
        return jsonify({"error": "item and qty are required"}), 400

    order_id = str(uuid.uuid4())
    order = {
        "order_id": order_id,
        "item": item,
        "qty": qty,
        "student_id": student_id,
        "status": "PLACED",
    }

    with orders_lock:
        orders[order_id] = order

    # Publish to RabbitMQ
    try:
        conn = get_connection(retries=3, delay=2)
        ch = conn.channel()
        setup_channel(ch)
        ch.basic_publish(
            exchange=EXCHANGE,
            routing_key="order.placed",
            body=json.dumps(order),
            properties=pika.BasicProperties(delivery_mode=2),  # persistent
        )
        conn.close()
        logger.info("Published OrderPlaced for order %s (%s x%s)", order_id, item, qty)
    except Exception as e:
        logger.error("Failed to publish OrderPlaced: %s", e)
        with orders_lock:
            orders[order_id]["status"] = "PUBLISH_FAILED"
        return jsonify({"order_id": order_id, "status": "PUBLISH_FAILED", "error": str(e)}), 500

    return jsonify({"order_id": order_id, "status": "PLACED"}), 201


@app.route("/order/<order_id>", methods=["GET"])
def get_order(order_id):
    """Get the status of a specific order."""
    with orders_lock:
        order = orders.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(order), 200


@app.route("/orders", methods=["GET"])
def list_orders():
    """List all orders."""
    with orders_lock:
        return jsonify(list(orders.values())), 200


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def graceful_shutdown(signum, frame):
    logger.info("Shutting down OrderService...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Start background status consumer
    consumer_thread = threading.Thread(target=status_consumer, daemon=True)
    consumer_thread.start()

    logger.info("OrderService starting on port 5001...")
    app.run(host="0.0.0.0", port=5001, debug=False)
