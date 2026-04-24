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
51 passed
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

## Step 8 Stress Tester Validation

Step 8 adds a local async stress tester using `httpx`. It can send concurrent `/generate` requests to a running backend and write CSV/JSON reports under `reports/`.

Run the tests:

```powershell
python -m pytest
```

Expected result:

```text
37 passed
```

These tests validate:

- the scenario registry contains `normal_load`
- empty result summaries work
- status code distributions are calculated
- CSV reports can be written
- JSON summaries can be written
- no running FastAPI server is required for unit tests

Start the backend in terminal 1:

```powershell
python -m uvicorn backend.main:app --reload
```

Optionally reset metrics in terminal 2:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/metrics/reset"
```

Run the stress tester:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario normal_load
```

Expected console output shape:

```text
Scenario: normal_load
Total requests: 100
Successful HTTP requests: ...
Failed HTTP requests: ...
Reports written to reports/latest_results.csv and reports/latest_summary.json
```

Check generated reports:

```powershell
Get-ChildItem reports
```

Expected files:

```text
latest_results.csv
latest_summary.json
```

View the summary:

```powershell
Get-Content reports/latest_summary.json
```

Expected important fields:

```json
{
  "total_requests": 100,
  "successful_http_requests": 100,
  "failed_http_requests": 0,
  "accepted_or_completed": 100,
  "queued": 0,
  "average_latency_seconds": 0.0
}
```

Exact values may vary depending on rate limits, queueing, and current server state.

Check backend metrics after the run:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
```

Expected counters should reflect the stress test traffic:

- `total_requests`
- `accepted_requests`
- `queued_requests`
- `completed_requests`
- `rejected_requests`
- `requests_by_user`
- `requests_by_model`

Available scenarios:

- `normal_load`
- `burst_load`
- `vip_protection`
- `abusive_user`
- `mixed_load`

Stress tester limitations:

- local async load generation only
- no distributed load generation
- no external load testing tools
- no Ollama backend yet

## Step 9 Stress Tester Polling Validation

Step 9 improves the stress tester so queued requests can be polled through `GET /requests/{request_id}` until they reach a final status or timeout. Reports now include both initial `/generate` latency and end-to-end latency.

Run the tests:

```powershell
python -m pytest
```

Expected result:

```text
40 passed
```

These tests validate:

- final backend status distributions are reported
- end-to-end latency percentiles are calculated
- timed-out final results are counted
- CSV output includes polling fields
- existing Step 1-8 behavior still works

Start the backend in terminal 1:

```powershell
python -m uvicorn backend.main:app --reload
```

Reset metrics in terminal 2:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/metrics/reset"
```

Run a polling-enabled stress test:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario burst_load `
  --poll-queued true `
  --poll-timeout 30
```

Polling is enabled by default. `--poll-queued false` disables result polling.

Expected console output shape:

```text
Scenario: burst_load
Total requests: 200
Successful HTTP requests: ...
Failed HTTP requests: ...
Reports written to reports/latest_results.csv and reports/latest_summary.json
```

Check the summary report:

```powershell
Get-Content reports/latest_summary.json
```

Look for Step 9 fields:

```json
{
  "completed_final": 0,
  "failed_final": 0,
  "timed_out_final": 0,
  "queued_initial": 0,
  "completed_immediate": 0,
  "average_end_to_end_latency_seconds": 0.0,
  "p50_end_to_end_latency_seconds": 0.0,
  "p95_end_to_end_latency_seconds": 0.0,
  "p99_end_to_end_latency_seconds": 0.0,
  "final_backend_status_distribution": {}
}
```

Exact values depend on server state, rate limits, queueing, and whether requests complete immediately.

Check the CSV header:

```powershell
Get-Content reports/latest_results.csv -TotalCount 1
```

Expected header includes:

```text
final_backend_status,final_latency_seconds,end_to_end_latency_seconds,polling_attempts,polling_error
```

Check backend metrics after the run:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
```

Expected counters should reflect the stress run:

- `total_requests`
- `accepted_requests`
- `queued_requests`
- `completed_requests`
- `rejected_requests`

Latency definitions:

- initial latency: time to receive the first `/generate` response
- end-to-end latency: time until a queued request reaches `completed`, `failed`, `rejected`, or `timed_out`

Current limitations:

- polling is local to the stress tester process
- no distributed load generation
- no external load testing tools
- no Ollama backend yet

## Step 10 Optional Ollama Backend Validation

Step 10 adds an optional Ollama backend adapter behind the existing architecture. Simulated models remain enabled. The Ollama model is disabled by default in `config/models.yaml`.

Run the tests:

```powershell
python -m pytest
```

Expected result:

```text
44 passed
```

These tests validate:

- backend selection returns `SimulatedLLMBackend` for simulated models
- unknown backend names are rejected
- `OllamaLLMBackend` works with mocked `httpx.AsyncClient`
- `/generate` rejects `ollama-llama` while `enabled: false`
- no Ollama installation or running server is required for tests

Start the backend:

```powershell
python -m uvicorn backend.main:app --reload
```

Confirm simulated models still work:

```powershell
$body = @{
  user_id = "user_standard_01"
  project_id = "standard_project"
  model = "simulated-small"
  prompt = "hello simulated"
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

Confirm Ollama is disabled by default:

```powershell
$body = @{
  user_id = "user_vip_01"
  project_id = "vip_project"
  model = "ollama-llama"
  prompt = "hello ollama"
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
400
{"detail":"model_disabled"}
```

Optional real Ollama check:

```powershell
ollama pull llama3.1
```

Then edit `config/models.yaml`:

```yaml
ollama-llama:
  backend: "ollama"
  enabled: true
  ollama_model: "llama3.1"
```

Restart the backend after changing config:

```powershell
python -m uvicorn backend.main:app --reload
```

Send an Ollama request:

```powershell
$body = @{
  user_id = "user_vip_01"
  project_id = "vip_project"
  model = "ollama-llama"
  prompt = "Say hello from Ollama"
  max_tokens = 64
} | ConvertTo-Json

$body

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/generate" `
  -ContentType "application/json" `
  -Body $body
```

The `$body` line should print JSON before sending the request. If FastAPI returns this error:

```json
{"detail":[{"type":"missing","loc":["body"],"msg":"Field required","input":null}]}
```

the request reached FastAPI without a JSON body. Recreate `$body` in the same PowerShell terminal and rerun the request.

Expected successful Ollama response:

```text
status  : completed
message : <text generated by llama3.1>
```

After testing, set `enabled: false` again unless you want Ollama active by default.

Current Ollama limitations:

- no streaming yet
- no advanced Ollama concurrency tuning yet
- tests use mocks and do not require Ollama installed or running

## Step 11 Ollama Stress Scenario And Comparison Report Validation

Step 11 adds Ollama-specific stress scenarios and comparison reporting by backend and model. Automated tests still do not require Ollama or a running FastAPI backend.

Run the tests:

```powershell
python -m pytest
```

Expected result:

```text
51 passed
```

These tests validate:

- `ollama_normal_load` exists
- `ollama_burst_load` exists
- summaries include `requests_by_model`
- summaries include `requests_by_backend`
- latency is grouped by model
- end-to-end latency is grouped by backend
- Markdown comparison reports can be written
- existing Step 1-10 behavior still works

Start the backend:

```powershell
python -m uvicorn backend.main:app --reload
```

Run a simulated scenario first:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario normal_load `
  --poll-queued true `
  --poll-timeout 30
```

Check generated reports:

```powershell
Get-ChildItem reports
```

Expected files:

```text
latest_results.csv
latest_summary.json
latest_comparison.md
```

Check the comparison report:

```powershell
Get-Content reports/latest_comparison.md
```

Expected sections:

```text
Requests By Backend
Requests By Model
Latency By Backend
Latency By Model
End-To-End Latency By Backend
End-To-End Latency By Model
```

Optional Ollama scenario validation:

1. Confirm Ollama has the model:

```powershell
ollama list
```

2. Ensure `config/models.yaml` has:

```yaml
ollama-llama:
  enabled: true
```

3. Restart the backend after changing config.

4. Run the Ollama scenario:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario ollama_normal_load `
  --poll-queued true `
  --poll-timeout 120
```

Expected console output shape:

```text
Scenario: ollama_normal_load
Total requests: 20
Reports written to reports/latest_results.csv, reports/latest_summary.json and reports/latest_comparison.md
```

Inspect the summary:

```powershell
Get-Content reports/latest_summary.json
```

Expected important fields:

```json
{
  "requests_by_backend": {
    "ollama": 20
  },
  "latency_by_backend": {
    "ollama": {
      "count": 20
    }
  }
}
```

Exact values may differ if requests are rejected, queued, failed, or rate-limited.

Ollama stress notes:

- Ollama must be running locally.
- `ollama-llama` must be manually enabled in config.
- Results depend heavily on CPU/GPU/RAM, model size, and Ollama configuration.
- Simulated and Ollama results are not directly equivalent; simulated latency is artificial.
