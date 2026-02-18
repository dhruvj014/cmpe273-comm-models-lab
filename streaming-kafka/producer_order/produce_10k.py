import json, os, time, uuid, random
from datetime import datetime, timezone
from confluent_kafka import Producer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:29092")
TOPIC = os.getenv("ORDER_TOPIC", "order-events")

ITEMS = ["burrito", "pizza", "salad", "taco"]
STUDENTS = [f"S{100+i}" for i in range(50)]

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def main():
    p = Producer({"bootstrap.servers": BOOTSTRAP, "linger.ms": 10, "batch.num.messages": 10000})
    start = time.time()

    for i in range(10_000):
        order_id = str(uuid.uuid4())
        event = {
            "event_type": "OrderPlaced",
            "event_id": str(uuid.uuid4()),
            "order_id": order_id,
            "student_id": random.choice(STUDENTS),
            "item_id": random.choice(ITEMS),
            "qty": random.randint(1, 3),
            "event_time": now_iso(),
        }
        p.produce(TOPIC, key=order_id, value=json.dumps(event).encode("utf-8"))
        if i % 5000 == 0 and i > 0:
            p.poll(0)

    p.flush()
    elapsed = time.time() - start
    print(f"Published 10000 events in {elapsed:.2f}s ({10000/elapsed:.2f} ev/s)")

if __name__ == "__main__":
    main()
