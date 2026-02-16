
# Synchronous REST Microservices Lab

This project implements a campus food ordering workflow using 3 synchronous HTTP microservices.

## Folder Structure
- `common/`: Shared utilities (IDs).
- `sync-rest/`: The synchronous REST implementation.
  - `order_service/`: Orchestrator.
  - `inventory_service/`: Inventory management with fault injection.
  - `notification_service/`: Zero-logic notification sender.
  - `tests/`: Integration tests and latency scripts.

## How to Run

1. **Build and Start Services**:
   ```bash
   cd sync-rest
   docker compose up --build
   ```
   Services will be available at:
   - Order Service: http://localhost:8000
   - Inventory Service: http://localhost:8001
   - Notification Service: http://localhost:8002

2. **Run Tests**:
   Open a new terminal in `sync-rest/tests`:
   ```bash
   cd sync-rest/tests
   pip install -r requirements.txt
   pytest test_happy_path.py
   ```

3. **Run Latency Test (Baseline)**:
   ```bash
   python latency_test.py Baseline
   ```

## Failure Injection Scenarios

### 1. High Latency (Timeout Test)
Inject a 2000ms delay in Inventory Service. Order Service times out after 1000ms.

**Command**:
```bash
# In sync-rest folder
docker compose stop inventory_service
# Override env var to set delay
docker compose run -e INVENTORY_DELAY_MS=2000 -p 8001:8001 --name sync-rest-inventory_service-1 -d inventory_service
# Note: The above might not reconnect to the network easily. 
# Easier way: Update docker-compose.yml or use:
docker compose down
# Edit docker-compose.yml to set INVENTORY_DELAY_MS=2000
docker compose up -d
```
*Wait for it to be healthy.*

**Test**:
```bash
python latency_test.py "High Latency"
# or
pytest test_failure_injection.py
```

### 2. Service Failure (Available/Consistency Test)
Force Inventory Service to fail (HTTP 500).

**Command**:
```bash
docker compose down
# Edit docker-compose.yml to set INVENTORY_FAIL_MODE=true
docker compose up -d
```

**Test**:
```bash
python latency_test.py "Forced Failure"
```

## Why Synchronous Calls Amplify Latency
In a synchronous chain (Order -> Inventory -> Notification), the total latency is the sum of all downstream latencies plus network overhead. If Inventory blocks for 2 seconds, Order Service is blocked for 2 seconds (or until timeout). This coupling reduces throughput and makes the system fragile to cascading failures.
