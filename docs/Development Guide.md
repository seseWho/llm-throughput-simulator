# Development Guide

This document describes how to verify the current project skeleton and what is intentionally not implemented yet.

## Scope

The current version is a basic Python MVP structure for an LLM high-throughput serving simulator.

Implemented:

- FastAPI application bootstrap.
- Basic health endpoint.
- Placeholder API routes.
- YAML configuration files.
- Minimal configuration loader.
- Pydantic request and response models.
- Placeholder modules for policies, queues, LLM backends, metrics, and stress testing.
- Minimal test coverage for config loading.

Not implemented yet:

- Real LLM generation logic.
- Queue admission logic.
- Priority scheduling.
- Rate limiting.
- Quota and budget enforcement.
- Cost calculation.
- Metrics aggregation.
- Stress testing.
- Ollama integration.

## Local Setup

Create and activate a virtual environment if desired.

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install the project with development dependencies:

```powershell
pip install -e ".[dev]"
```

## Mini-Check Before Development

Run the test suite:

```powershell
python -m pytest
```

Expected result:

```text
1 passed
```

Start the FastAPI backend:

```powershell
python -m uvicorn backend.main:app --reload
```

By default, the API runs at:

```text
http://127.0.0.1:8000
```

## Smoke Test Endpoints

In another terminal, check the health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok"
}
```

Check the config summary endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/config/summary
```

Expected behavior:

- Returns a non-empty response.
- Includes the configured YAML files:
  - `users.yaml`
  - `projects.yaml`
  - `models.yaml`
  - `limits.yaml`
  - `degradation.yaml`

Check the placeholder generation endpoint:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/generate `
  -ContentType "application/json" `
  -Body '{"user_id":"user_standard_01","project_id":"standard_project","model":"simulated-small","prompt":"hello","max_tokens":64}'
```

Expected behavior:

- Returns a placeholder response.
- `status` should be `accepted`.
- No real LLM backend is called.

## Configuration Files

All runtime configuration currently lives under `config/`.

- `users.yaml`: user definitions and project membership.
- `projects.yaml`: project plans, priorities, quotas, budgets, and concurrency limits.
- `models.yaml`: available model definitions and backend metadata.
- `limits.yaml`: global limits, rate limits, and priority weights.
- `degradation.yaml`: pressure levels and degradation actions.

At this stage, config files are loaded but not fully validated against strict schemas.

## Development Rules

- Keep new modules small and testable.
- Add at least one basic test for each new feature.
- Keep business rules in config when they are meant to be tunable.
- Do not connect to Ollama until the backend interface is defined.
- Do not implement stress testing until the main request path has enough behavior to test.
- Prefer incremental implementation over broad refactors.

## Suggested Implementation Order

1. Add stronger config validation.
2. Implement the simulated backend.
3. Add simple token estimation.
4. Implement cost calculation.
5. Implement quota manager.
6. Implement rate limiter.
7. Implement admission controller.
8. Implement priority queue behavior.
9. Add metrics collection.
10. Add stress tester scenarios.
11. Integrate Ollama behind the backend interface.

## Troubleshooting

If `pytest` is not found, install development dependencies:

```powershell
pip install -e ".[dev]"
```

If `uvicorn` is not found as a command, run it through Python:

```powershell
python -m uvicorn backend.main:app --reload
```

If `/config/summary` fails, check that the command is being run from the repository root so the relative `config/` directory can be found.
