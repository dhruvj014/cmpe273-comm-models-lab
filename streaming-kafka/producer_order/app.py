import json, os, time, uuid
from datetime import datetime, timezone
from confluent_kafka import Producer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
TOPIC = os.getenv("ORDER_TOPIC", "order-events")

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def delivery_report(err, msg):
    if err:
        print(f"DELIVERY FAILED: {err}")
    else:
        pass

def main():
    p = Producer({"bootstrap.servers": BOOTSTRAP})
    print(f"Producer connected to {BOOTSTRAP}, topic={TOPIC}")

    # publish a small heartbeat order every 5 seconds (nice for smoke)
    while True:
        order_id = str(uuid.uuid4())
        event = {
            "event_type": "OrderPlaced",
            "event_id": str(uuid.uuid4()),
            "order_id": order_id,
            "student_id": "S123",
            "item_id": "burrito",
            "qty": 1,
            "event_time": now_iso(),
        }
        p.produce(TOPIC, key=order_id, value=json.dumps(event).encode("utf-8"), callback=delivery_report)
        p.poll(0)
        print(f"Produced OrderPlaced order_id={order_id}")
        time.sleep(5)

if __name__ == "__main__":
    main()
