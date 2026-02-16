
import httpx
import time
import statistics
import asyncio
import sys

# Configuration
URL = "http://localhost:8000/order"
N = 100
WORKERS = 1 # Sequential for clear synchronous measurement, or concurrent?
# "Sends N requests" - usually implies sequential or parallel. 
# For "latency impact of sync calls", sequential is clearest, or low concurrency.
# Let's do sequential to measure pure request latency experienced by client.

async def send_request(client, i):
    payload = {"user_id": f"u{i}", "item_id": "burger", "quantity": 1}
    start = time.time()
    try:
        response = await client.post(URL, json=payload, timeout=10.0)
        latency = (time.time() - start) * 1000
        return latency, response.status_code
    except Exception as e:
        latency = (time.time() - start) * 1000
        return latency, 0

async def measure_latency(scenario_name):
    print(f"--- Running Scenario: {scenario_name} (N={N}) ---")
    latencies = []
    success_count = 0
    
    async with httpx.AsyncClient() as client:
        for i in range(N):
            lat, status = await send_request(client, i)
            latencies.append(lat)
            if status == 200:
                success_count += 1
            print(f"Req {i+1}/{N}: {lat:.2f}ms (Status: {status})", end="\r")
    
    print()
    
    if not latencies:
        print("No requests completed.")
        return

    avg_lat = statistics.mean(latencies)
    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
    success_rate = (success_count / N) * 100
    
    # Append to results.md
    with open("results.md", "a") as f:
        f.write(f"| {scenario_name} | {N} | {avg_lat:.2f} | {p50:.2f} | {p95:.2f} | {success_rate:.1f}% | |\n")

    print(f"Results: Avg={avg_lat:.2f}ms, P95={p95:.2f}ms, Success={success_rate}%")

if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "Baseline"
    
    # Initialize results.md if not exists
    try:
        with open("results.md", "x") as f:
             f.write("| Scenario | N | Avg(ms) | P50(ms) | P95(ms) | Success% | Notes |\n")
             f.write("|---|---|---|---|---|---|---|\n")
    except FileExistsError:
        pass

    asyncio.run(measure_latency(scenario))
