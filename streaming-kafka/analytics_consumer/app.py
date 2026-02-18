import json, os, signal
from datetime import datetime
from confluent_kafka import Consumer, KafkaException

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
ORDER_TOPIC = os.getenv("ORDER_TOPIC", "order-events")
INVENTORY_TOPIC = os.getenv("INVENTORY_TOPIC", "inventory-events")
GROUP_ID = os.getenv("GROUP_ID", "analytics-service")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "/app/metrics_report.json")
FLUSH_EVERY = int(os.getenv("FLUSH_EVERY", "2000"))

running = True

def handle_sig(*_):
    global running
    running = False

signal.signal(signal.SIGINT, handle_sig)
signal.signal(signal.SIGTERM, handle_sig)

def minute_bucket(iso_ts: str) -> str:
    # assumes ISO8601 "....Z"
    # bucket to YYYY-MM-DDTHH:MMZ
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%dT%H:%MZ")

def write_report(path, orders_per_minute, total_orders, reserved, failed):
    denom = (reserved + failed)
    failure_rate = (failed / denom) if denom else 0.0
    report = {
        "total_orders": total_orders,
        "total_reserved": reserved,
        "total_failed": failed,
        "failure_rate": round(failure_rate, 6),
        "orders_per_minute": orders_per_minute,
    }
    with open(path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)

def main():
    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    })

    consumer.subscribe([ORDER_TOPIC, INVENTORY_TOPIC])
    print(f"[analytics] consuming {ORDER_TOPIC},{INVENTORY_TOPIC} group={GROUP_ID}")
    print(f"[analytics] writing report to {OUTPUT_FILE}")

    orders_per_minute = {}
    total_orders = 0
    reserved = 0
    failed = 0
    seen = 0

    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                # Transient errors can happen during startup or topic creation.
                # Don't crash the container; just log and continue polling.
                print(f"[analytics] kafka poll error: {msg.error()}")
                continue


            seen += 1
            event = json.loads(msg.value().decode("utf-8"))
            et = event.get("event_type")

            if et == "OrderPlaced":
                total_orders += 1
                b = minute_bucket(event["event_time"])
                orders_per_minute[b] = orders_per_minute.get(b, 0) + 1

            elif et == "InventoryReserved":
                reserved += 1
            elif et == "InventoryFailed":
                failed += 1

            if seen % FLUSH_EVERY == 0:
                write_report(OUTPUT_FILE, orders_per_minute, total_orders, reserved, failed)
                print(f"[analytics] checkpoint seen={seen} orders={total_orders} reserved={reserved} failed={failed}")

    finally:
        write_report(OUTPUT_FILE, orders_per_minute, total_orders, reserved, failed)
        consumer.close()
        print("[analytics] final report written")

if __name__ == "__main__":
    main()
