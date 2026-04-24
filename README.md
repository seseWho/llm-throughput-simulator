# llm-load-mvp

Python MVP project for simulating high-throughput LLM serving behavior.

## Project Goal

This project provides the initial structure for an LLM high-throughput serving simulator. The current goal is to establish a clean backend layout, configuration foundation, placeholder policy and queue components, and minimal API endpoints.

## Architecture Summary

- `backend/`: FastAPI application, API routes, config loading, request and response models.
- `backend/policies/`: placeholders for rate limiting, quota, cost, and policy logic.
- `backend/queue/`: placeholders for admission control, priority scheduling, and queue management.
- `backend/llm_backends/`: placeholders for simulated and Ollama-backed LLM providers.
- `backend/metrics/`: placeholder metrics collection.
- `stress_tester/`: placeholders for future load generation, scenarios, and reporting.
- `config/`: YAML configuration for users, projects, models, limits, and degradation levels.
- `tests/`: minimal tests for the configuration loader.

## Install Dependencies

```bash
pip install -e ".[dev]"
```

## Run the FastAPI Backend

```bash
uvicorn backend.main:app --reload
```

The health endpoint is available at:

```text
GET /health
GET /queue/status
GET /requests/{request_id}
GET /metrics
POST /metrics/reset
```

## Development Notes

See [docs/development-guide.md](docs/development-guide.md) for setup, mini-check commands, endpoint smoke tests, current limitations, and suggested next implementation steps.

## Current Status

Step 9 is implemented: the stress tester now polls queued requests until completion, failure, rejection, or timeout so reports include end-to-end behavior.

Implemented foundations:

- simulated LLM backend
- user/project/model validation
- simple request rate limiting
- in-memory project token quota tracking
- estimated token cost calculation
- admission control
- in-memory priority queue foundation
- background queue workers
- queue status endpoint
- request status endpoint
- metrics summary endpoint
- metrics reset endpoint
- local async stress tester
- CSV and JSON stress test reports
- queued request polling in stress tester
- end-to-end latency reporting

Current limitations:

- usage is stored in memory only
- rate limiting uses a simple fixed window
- queue is in-memory only
- no persistence yet
- queue and results are lost on restart
- metrics are in-memory only
- metrics are lost on restart
- no distributed queue
- no distributed workers
- no Prometheus or Grafana integration yet
- no persistent reporting yet
- local async stress tester only
- no distributed load generation
- no Ollama integration yet

## Generate Example

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_standard_01",
    "project_id": "standard_project",
    "model": "simulated-small",
    "prompt": "Hello from the simulator",
    "max_tokens": 64
  }'
```

If a request is queued, use the returned `request_id` to check its status:

```bash
curl http://127.0.0.1:8000/requests/<request_id>
```

## Stress Tester

Start the backend:

```bash
uvicorn backend.main:app --reload
```

Run a scenario:

```bash
python -m stress_tester.load_generator --base-url http://localhost:8000 --scenario burst_load --poll-queued true --poll-timeout 30
```

Available scenarios:

- `normal_load`
- `burst_load`
- `vip_protection`
- `abusive_user`
- `mixed_load`

Reports are written to:

- `reports/latest_results.csv`
- `reports/latest_summary.json`

Polling is enabled by default. Initial latency is the time to receive the first `/generate` response. End-to-end latency is the time until a queued request reaches a final status such as `completed`, `failed`, `rejected`, or `timed_out`.

## Future Steps

1. implement config validation
2. implement persistent reporting
3. integrate Ollama
