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
32 passed
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
$body = @{
  user_id = "user_standard_01"
  project_id = "standard_project"
  model = "simulated-small"
  prompt = "hello"
  max_tokens = 64
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/generate" `
  -ContentType "application/json" `
  -Body $body
```

Expected behavior:

- Returns a simulated generation response.
- `status` should be `completed`.
- `estimated_input_tokens`, `estimated_output_tokens`, and `estimated_cost_eur` should be populated.
- No real LLM backend is called.

You can also test the endpoint through the FastAPI docs:

```text
http://127.0.0.1:8000/docs
```

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

If the server logs show this after opening the browser at the base URL:

```text
GET / HTTP/1.1" 404 Not Found
GET /favicon.ico HTTP/1.1" 404 Not Found
```

That is expected. The project does not define a root HTML page yet. Use `/health`, `/config/summary`, `/generate`, or `/docs`.

If `/generate` returns:

```text
422 Unprocessable Content
```

FastAPI received the request, but the JSON body did not match the required `GenerateRequest` schema. Make sure the body includes:

```json
{
  "user_id": "user_standard_01",
  "project_id": "standard_project",
  "model": "simulated-small",
  "prompt": "hello",
  "max_tokens": 64
}
```

In PowerShell, prefer building the request body with a hashtable and `ConvertTo-Json`, as shown in the smoke test above.

## Step 4 Policy Engine Validation

Step 4 adds the Policy Engine foundation before the simulated backend. A valid `/generate` request now passes through:

- user validation
- project validation
- user/project ownership validation
- model validation
- simple rate limiting
- in-memory quota checking
- cost estimation

Run the tests first:

```powershell
python -m pytest
```

Expected result:

```text
14 passed
```

Start the API:

```powershell
python -m uvicorn backend.main:app --reload
```

Send a valid request:

```powershell
$body = @{
  user_id = "user_standard_01"
  project_id = "standard_project"
  model = "simulated-small"
  prompt = "hello from step 4"
  max_tokens = 64
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/generate" `
  -ContentType "application/json" `
  -Body $body
```

Expected behavior:

- HTTP `200`
- `status` is `completed`
- token estimates are populated
- estimated cost is greater than or equal to zero

Send an invalid user request:

```powershell
$body = @{
  user_id = "missing_user"
  project_id = "standard_project"
  model = "simulated-small"
  prompt = "hello"
  max_tokens = 64
} | ConvertTo-Json

try {
  Invoke-WebRequest `
    -Method Post `
    -Uri "http://127.0.0.1:8000/generate" `
    -ContentType "application/json" `
    -Body $body
} catch {
  $_.Exception.Response.StatusCode.value__
  $_.ErrorDetails.Message
}
```

Expected response:

```text
403
{"detail":"unknown_user"}
```

Send a project mismatch request:

```powershell
$body = @{
  user_id = "user_standard_01"
  project_id = "vip_project"
  model = "simulated-small"
  prompt = "hello"
  max_tokens = 64
} | ConvertTo-Json

try {
  Invoke-WebRequest `
    -Method Post `
    -Uri "http://127.0.0.1:8000/generate" `
    -ContentType "application/json" `
    -Body $body
} catch {
  $_.Exception.Response.StatusCode.value__
  $_.ErrorDetails.Message
}
```

Expected response:

```text
403
{"detail":"project_mismatch"}
```

PowerShell note: `Invoke-RestMethod` and `Invoke-WebRequest` report non-2xx HTTP responses as exceptions. That does not mean the API failed. For negative validation checks, the exception is expected; inspect the status code and JSON detail in the `catch` block.

## Step 5 Admission And Queue Validation

Step 5 adds the Admission Controller and Priority Queue foundation. A valid `/generate` request now follows this path:

```text
Policy Engine -> Admission Controller -> immediate processing or queue or reject
```

Run the tests:

```powershell
python -m pytest
```

Expected result:

```text
21 passed
```

These tests validate:

- admission accepts when active capacity is available
- admission queues when active capacity is full and queue capacity exists
- admission rejects when active capacity and queue capacity are both full
- high project priority scores above normal priority
- interactive requests score above batch requests with the same project priority
- the queue dequeues higher priority before lower priority
- `/queue/status` returns the expected fields
- `/generate` still works for a valid `simulated-small` request

Start the API:

```powershell
python -m uvicorn backend.main:app --reload
```

Check queue status:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/queue/status"
```

Expected response shape:

```text
queue_size          : 0
active_requests     : 0
max_active_requests : 50
max_queue_size      : 1000
```

Send a valid request:

```powershell
$body = @{
  user_id = "user_standard_01"
  project_id = "standard_project"
  model = "simulated-small"
  prompt = "hello from step 5"
  max_tokens = 64
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/generate" `
  -ContentType "application/json" `
  -Body $body
```

Expected behavior:

- HTTP `200`
- `status` is `completed`
- `/queue/status` should usually still show `queue_size` as `0`

Manual queue-path note: the default `config/limits.yaml` has `max_active_requests: 50`, so ordinary manual testing usually processes requests immediately. The queue path is covered by tests in this step. Queued requests are stored in memory but are not processed by background workers yet.

## Step 6 Background Worker Validation

Step 6 adds in-memory background workers for queued requests. The request path is now:

```text
Policy Engine -> Admission Controller -> immediate processing or queue -> background worker -> result lookup
```

Run the tests:

```powershell
python -m pytest
```

Expected result:

```text
26 passed
```

These tests validate:

- queue result storage
- failed request marking
- a worker can process one queued simulated request
- `/requests/{request_id}` returns `not_found` for unknown IDs
- `/generate` can return `queued` when capacity is saturated
- existing Step 1-5 behavior still works

Start the API:

```powershell
python -m uvicorn backend.main:app --reload
```

Check queue and worker status:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/queue/status"
```

Expected response shape:

```text
queue_size          : 0
active_requests     : 0
max_active_requests : 50
max_queue_size      : 1000
worker_running      : True
worker_count        : 3
completed_requests  : 0
failed_requests     : 0
```

Check an unknown request ID:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/requests/unknown-id"
```

Expected response:

```text
request_id : unknown-id
status     : not_found
message    : Request not found
```

Send a valid request:

```powershell
$body = @{
  user_id = "user_standard_01"
  project_id = "standard_project"
  model = "simulated-small"
  prompt = "hello from step 6"
  max_tokens = 64
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/generate" `
  -ContentType "application/json" `
  -Body $body
```

Expected behavior:

- HTTP `200`
- `status` is usually `completed`

If a request returns `queued`, copy the returned `request_id` and check it:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/requests/<request_id>"
```

Possible statuses:

- `queued`
- `processing`
- `completed`
- `failed`
- `not_found`

Manual queue-path note: the default `config/limits.yaml` has `max_active_requests: 50`, so ordinary manual requests usually process immediately. The background worker path is covered by automated tests in this step. Workers, queue state, and request results are in-memory only and are lost when the FastAPI process restarts.

## Step 7 Metrics Validation

Step 7 adds in-memory metrics collection for the simulator. Metrics are updated by both immediate `/generate` processing and background worker completions.

Run the tests:

```powershell
python -m pytest
```

Expected result:

```text
32 passed
```

These tests validate:

- metrics start with zero counters
- received requests increment `total_requests`
- queued requests increment `queued_requests`
- completed requests increment completion, token, and cost totals
- latency fields are present in the summary
- `POST /metrics/reset` resets counters
- existing Step 1-6 behavior still works

Start the API:

```powershell
python -m uvicorn backend.main:app --reload
```

Reset metrics:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/metrics/reset"
```

Expected response:

```text
status  : ok
message : Metrics reset
```

Check empty metrics:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
```

Expected important fields:

```text
total_requests     : 0
completed_requests : 0
queued_requests    : 0
failed_requests    : 0
```

Send a valid request:

```powershell
$body = @{
  user_id = "user_standard_01"
  project_id = "standard_project"
  model = "simulated-small"
  prompt = "hello from step 7"
  max_tokens = 64
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/generate" `
  -ContentType "application/json" `
  -Body $body
```

Expected behavior:

- HTTP `200`
- `status` is `completed`

Check metrics again:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
```

Expected important fields:

```text
total_requests           : 1
accepted_requests        : 1
completed_requests       : 1
total_input_tokens       : greater than 0
total_output_tokens      : 64
total_estimated_cost_eur : greater than or equal to 0
average_latency_seconds  : not empty
p50_latency_seconds      : not empty
requests_by_user         : includes user_standard_01
requests_by_project      : includes standard_project
requests_by_model        : includes simulated-small
```

Metrics limitations:

- metrics are in-memory only
- metrics are lost when the FastAPI process restarts
- there is no Prometheus or Grafana integration yet
- there is no persistent reporting yet
