import json, os, time, uuid
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer, KafkaException

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
ORDER_TOPIC = os.getenv("ORDER_TOPIC", "order-events")
INVENTORY_TOPIC = os.getenv("INVENTORY_TOPIC", "inventory-events")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "dlq-order-events")
GROUP_ID = os.getenv("GROUP_ID", "inventory-service")
THROTTLE_MS = int(os.getenv("THROTTLE_MS", "0"))

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def to_dlq(producer: Producer, raw: bytes, err: str):
    payload = {
        "event_type": "PoisonOrderEvent",
        "event_id": str(uuid.uuid4()),
        "error": err,
        "raw": raw.decode("utf-8", errors="replace"),
        "event_time": now_iso()
    }
    producer.produce(DLQ_TOPIC, value=json.dumps(payload).encode("utf-8"))
    producer.flush(5)

def main():
    # simple in-memory stock
    stock = {"burrito": 5000, "pizza": 5000, "salad": 5000, "taco": 5000}

    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    producer = Producer({"bootstrap.servers": BOOTSTRAP})

    consumer.subscribe([ORDER_TOPIC])
    print(f"[inventory] consuming {ORDER_TOPIC} as group={GROUP_ID}, throttle={THROTTLE_MS}ms")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                # Transient errors can happen during startup or topic creation.
                # Don't crash the container; just log and continue polling.
                print(f"[inventory] kafka poll error: {msg.error()}")
                continue


            raw = msg.value()
            if THROTTLE_MS > 0:
                time.sleep(THROTTLE_MS / 1000.0)

            try:
                event = json.loads(raw.decode("utf-8"))
                if event.get("event_type") != "OrderPlaced":
                    raise ValueError("unexpected event_type")

                order_id = event["order_id"]
                item_id = event["item_id"]
                qty = int(event["qty"])

                # reserve logic
                if stock.get(item_id, 0) >= qty:
                    stock[item_id] -= qty
                    out = {
                        "event_type": "InventoryReserved",
                        "event_id": str(uuid.uuid4()),
                        "order_id": order_id,
                        "item_id": item_id,
                        "qty": qty,
                        "status": "reserved",
                        "event_time": now_iso(),
                    }
                else:
                    out = {
                        "event_type": "InventoryFailed",
                        "event_id": str(uuid.uuid4()),
                        "order_id": order_id,
                        "item_id": item_id,
                        "qty": qty,
                        "status": "failed",
                        "reason": "out_of_stock",
                        "event_time": now_iso(),
                    }

                producer.produce(INVENTORY_TOPIC, key=order_id, value=json.dumps(out).encode("utf-8"))
                producer.flush(5)

                consumer.commit(message=msg)  # commit AFTER producing result
            except Exception as e:
                print(f"[inventory] poison message -> DLQ: {e}")
                to_dlq(producer, raw, str(e))
                consumer.commit(message=msg)  # commit so it doesn't block the partition

    finally:
        consumer.close()

if __name__ == "__main__":
    main()
