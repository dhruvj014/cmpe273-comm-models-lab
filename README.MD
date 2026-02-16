
# CMPE-273: Communication Models Lab

**Team:** DS-Team 8  
**Topic:** Week 2 - Architecture & Communication

## Part A: Synchronous REST Implementation

We implemented a "campus food ordering" workflow using 3 synchronous HTTP microservices:
*   **Order Service**: Accepting orders and orchestrating calls.
*   **Inventory Service**: Managing stock with configurable delay and failure injection.
*   **Notification Service**: Simulating notification delivery.

### Latency Test Results

| Scenario | N | Avg (ms) | P50 (ms) | P95 (ms) | Success % | Analysis |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **Baseline** | 100 | 71.07 | 71.97 | 89.07 | 50.0% | Baseline performance. |
| **High Latency** (2s Inventory Delay) | 100 | 1022.79 | 1022.22 | 1024.43 | 0.0% | **Timeout**: Order Service has a 1s timeout, causing all requests to fail when Inventory takes 2s. |
| **Forced Failure** (Inventory 500) | 100 | 61.62 | 68.70 | 75.00 | 0.0% | **Cascading Failure**: Failures in the Inventory Service propagate upstream to the Order Service immediately. |

### Key Observations
1.  **Timeouts**: In a synchronous chain, latency adds up. We set a 1000ms timeout on the Order Service to prevent indefinite blocking, which is why the "2s Delay" scenario resulted in 100% failure (timeouts).
2.  **Coupling**: The Order Service cannot function without the Inventory Service. When Inventory fails or is slow, the Order Service immediately degrades.

## Project Structure
*   `common/`: Shared utilities.
*   `sync-rest/`: Synchronous implementation (Code, Docker, Tests).

## How to Run
See [sync-rest/README.md](sync-rest/README.md) for detailed instructions.