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
```

## Development Notes

See [docs/Development Guide.md](docs/Development%20Guide.md) for setup, mini-check commands, endpoint smoke tests, current limitations, and suggested next implementation steps.

## Current Status

Step 5 is implemented: the `/generate` endpoint now evaluates policy, then uses an Admission Controller to either process immediately, enqueue, or reject. A simple in-memory priority queue foundation is available for queued requests.

Implemented foundations:

- simulated LLM backend
- user/project/model validation
- simple request rate limiting
- in-memory project token quota tracking
- estimated token cost calculation
- admission control
- in-memory priority queue foundation
- queue status endpoint

Current limitations:

- usage is stored in memory only
- rate limiting uses a simple fixed window
- queued requests are stored but not processed by background workers yet
- queue is in-memory only
- no persistence yet
- no distributed queue
- no Ollama integration yet
- no stress tester yet

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

## Future Steps

1. implement config validation
2. implement rate limiter
3. implement quota manager
4. implement background queue workers
5. implement stress tester
6. integrate Ollama
