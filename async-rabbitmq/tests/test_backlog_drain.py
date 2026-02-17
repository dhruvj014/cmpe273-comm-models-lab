"""
test_backlog_drain.py — Kill InventoryService for 60 seconds, keep publishing orders,
then restart and show the backlog drains from the inventory_queue.
"""

import json
import subprocess
import sys
import time

import requests

ORDER_URL = "http://localhost:5001/order"
ORDERS_URL = "http://localhost:5001/orders"
RABBITMQ_API = "http://localhost:15672/api/queues/%2F/inventory_queue"
RABBITMQ_AUTH = ("guest", "guest")
NUM_ORDERS = 20


def run_docker(cmd: str):
    """Run a docker compose command."""
    result = subprocess.run(
        f"docker compose {cmd}",
        shell=True,
        capture_output=True,
        text=True,
        cwd="../",  # run from async-rabbitmq/
    )
    return result


def get_queue_depth() -> int:
    """Get the number of messages in inventory_queue via RabbitMQ Management API."""
    try:
        r = requests.get(RABBITMQ_API, auth=RABBITMQ_AUTH, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data.get("messages", 0)
    except Exception as e:
        print(f"  Warning: Could not query RabbitMQ API: {e}")
    return -1


def main():
    print("=" * 60)
    print("BACKLOG DRAIN TEST")
    print("=" * 60)

    # Step 1: Stop inventory service
    print("\n[1] Stopping inventory_service...")
    run_docker("stop inventory_service")
    time.sleep(3)
    print("    inventory_service stopped.")

    # Step 2: Publish orders
    print(f"\n[2] Sending {NUM_ORDERS} orders while inventory_service is down...")
    order_ids = []
    for i in range(1, NUM_ORDERS + 1):
        payload = {"item": "burger", "qty": 1, "student_id": f"student-{i}"}
        try:
            r = requests.post(ORDER_URL, json=payload, timeout=10)
            data = r.json()
            oid = data.get("order_id", "???")
            order_ids.append(oid)
            print(f"    Order {i:>2}/{NUM_ORDERS} placed: order_id={oid[:12]}... status={data.get('status')}")
        except Exception as e:
            print(f"    Order {i:>2}/{NUM_ORDERS} FAILED: {e}")
        time.sleep(0.5)

    # Step 3: Check queue depth before restart
    time.sleep(2)
    depth = get_queue_depth()
    print(f"\n[3] Messages in inventory_queue before restart: {depth}")

    # Step 4: Restart inventory service
    print("\n[4] Restarting inventory_service...")
    run_docker("start inventory_service")

    # Step 5: Poll queue depth until drained
    print("\n[5] Monitoring queue drain...")
    for i in range(1, 13):  # poll for up to 60s
        time.sleep(5)
        depth = get_queue_depth()
        elapsed = i * 5
        print(f"    [+{elapsed:>2}s] Queue depth: {depth}")
        if depth == 0:
            break

    if depth == 0:
        print("\n    ✅ Backlog drained successfully!")
    else:
        print(f"\n    ⚠️  WARNING: {depth} messages remain in queue.")

    # Step 6: Check final order statuses
    print("\n[6] Final order statuses:")
    time.sleep(3)  # give status updates time to propagate
    try:
        r = requests.get(ORDERS_URL, timeout=10)
        all_orders = r.json()
        confirmed = sum(1 for o in all_orders if o.get("status") == "CONFIRMED")
        failed = sum(1 for o in all_orders if o.get("status") == "FAILED")
        placed = sum(1 for o in all_orders if o.get("status") == "PLACED")
        print(f"    Total: {len(all_orders)} | CONFIRMED: {confirmed} | FAILED: {failed} | PLACED: {placed}")
        # Show a few sample statuses
        for o in all_orders[:5]:
            print(f"    {o['order_id'][:12]}... → {o['status']}")
        if len(all_orders) > 5:
            print(f"    ... and {len(all_orders) - 5} more")
    except Exception as e:
        print(f"    Could not fetch orders: {e}")

    print("\n" + "=" * 60)
    print("BACKLOG DRAIN TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
