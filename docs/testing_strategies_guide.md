# Testing Strategies Guide

This guide explains how to test practical behavior combinations in the LLM high-throughput serving simulator. It focuses on experiments you can run with the current FastAPI backend, YAML configuration, stress tester, metrics, reports, degradation policies, and SQLite usage accounting.

The goal is not only to check that endpoints work. The goal is to compare strategies: immediate processing vs queueing, standard vs VIP traffic, simulated backend vs Ollama, normal operation vs degradation, and in-memory metrics vs persisted usage records.

## Prerequisites

Install development dependencies:

```powershell
pip install -e ".[dev]"
```

Run the tests:

```powershell
python -m pytest
```

Start the backend:

```powershell
python -m uvicorn backend.main:app --reload
```

The backend runs at:

```text
http://127.0.0.1:8000
```

Useful reset command before experiments:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/metrics/reset"
```

Metrics reset does not clear SQLite usage records. SQLite persistence is stored in:

```text
data/usage.db
```

## A. Baseline Simulated Load

Use this experiment to establish a clean baseline with the simulated backend.

Command:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario normal_load `
  --poll-queued true `
  --poll-timeout 30
```

Expected behavior:

- Most requests should complete successfully.
- Queue size should usually remain low with default limits.
- End-to-end latency should be close to simulated backend latency.
- Rejections should be low or zero unless limits were changed.

Inspect:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
Invoke-RestMethod "http://127.0.0.1:8000/queue/status"
Invoke-RestMethod "http://127.0.0.1:8000/usage/summary"
```

Reports:

```text
reports/latest_results.csv
reports/latest_summary.json
reports/latest_comparison.md
```

Key metrics:

- `completed_requests`
- `rejected_requests`
- `average_latency_seconds`
- `p95_latency_seconds`
- `queue_size`
- `records_by_status`

## B. Burst Traffic

Use this experiment to test short, high-pressure traffic.

Command:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario burst_load `
  --poll-queued true `
  --poll-timeout 30
```

Expected behavior:

- Requests may complete immediately, queue, or be rejected depending on `config/limits.yaml`.
- Queue size should increase during the burst.
- End-to-end latency should become higher than initial latency for queued requests.
- If queue capacity is exhausted, some requests should be rejected.

Inspect:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/queue/status"
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
Get-Content reports/latest_summary.json
```

Key metrics:

- `queued_requests`
- `rejected_requests`
- `queue_size`
- `active_requests`
- `queued_initial`
- `average_end_to_end_latency_seconds`
- `p95_end_to_end_latency_seconds`

## C. VIP Protection

Use this experiment to compare standard and VIP behavior when both submit traffic.

Command:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario vip_protection `
  --poll-queued true `
  --poll-timeout 30
```

Expected behavior:

- VIP traffic should receive higher priority scores than standard traffic.
- Under pressure, VIP requests should be more likely to complete or queue favorably.
- Standard traffic may see more queueing, higher end-to-end latency, or more rejections depending on limits.

How to compare VIP vs standard latency:

1. Open `reports/latest_results.csv`.
2. Filter by `user_id`.
3. Compare `user_vip_01` against `user_standard_01`.
4. Compare:
   - `latency_seconds`
   - `end_to_end_latency_seconds`
   - `final_backend_status`
   - `http_status`

Useful PowerShell check:

```powershell
Import-Csv reports/latest_results.csv |
  Group-Object user_id |
  Select-Object Name, Count
```

Key metrics:

- final status by user
- end-to-end latency by user
- status distribution by user
- `requests_by_user`
- `records_by_user`

## D. Rate Limiting

Use the abusive user scenario to test rate limiting behavior.

Command:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario abusive_user `
  --poll-queued true `
  --poll-timeout 30
```

Expected behavior:

- Once the simple per-user request window is exceeded, requests should be rejected.
- Rate-limit or policy rejections should return non-2xx HTTP responses.
- Stress tester results should record those responses instead of crashing.

Inspect:

```powershell
Get-Content reports/latest_summary.json
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
Invoke-RestMethod "http://127.0.0.1:8000/usage/recent?limit=20"
```

Key metrics:

- `rejected_requests`
- `status_code_distribution`
- `backend_status_distribution`
- `records_by_status`
- recent usage records with rejected status

Note: rate limiting is currently in-memory and uses a simple fixed or sliding window style implementation. Restarting the backend resets rate-limit state.

## E. Token Quota Exhaustion

Use this experiment to verify project token quota enforcement.

Temporarily reduce a quota in `config/projects.yaml`:

```yaml
standard_project:
  monthly_token_quota: 100
```

Restart the backend after editing config:

```powershell
python -m uvicorn backend.main:app --reload
```

Send repeated requests:

```powershell
$body = @{
  user_id = "user_standard_01"
  project_id = "standard_project"
  model = "simulated-small"
  prompt = "This request is used to consume project quota quickly."
  max_tokens = 64
  request_type = "interactive"
} | ConvertTo-Json

1..10 | ForEach-Object {
  try {
    Invoke-RestMethod `
      -Method Post `
      -Uri "http://127.0.0.1:8000/generate" `
      -ContentType "application/json" `
      -Body $body
  } catch {
    $_.Exception.Response.StatusCode.value__
    $_.ErrorDetails.Message
  }
}
```

Expected behavior:

- Early requests should complete or queue.
- Once quota is exceeded, later requests should be rejected.
- Quota state is currently in-memory, so restarting the backend resets the in-memory quota manager.

Inspect:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
Invoke-RestMethod "http://127.0.0.1:8000/usage/project/standard_project"
Invoke-RestMethod "http://127.0.0.1:8000/usage/recent?limit=20"
```

After the test, restore the original quota.

## F. Degradation Strategy

Degradation is based on queue usage:

```text
queue_usage_ratio = queue_size / max_queue_size
```

Configured levels:

- `normal`: no degradation actions.
- `soft_pressure`: reduce max tokens.
- `high_pressure`: reduce max tokens and reject batch traffic.
- `critical_pressure`: reduce max tokens, reject batch traffic, reject standard traffic, and preserve high-priority traffic.

Check current degradation state:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/queue/status"
```

Important fields:

- `current_degradation_level`
- `current_degradation_level_number`
- `queue_usage_ratio`
- `degradation_actions`

To trigger degradation quickly, temporarily reduce `config/limits.yaml`:

```yaml
global_limits:
  max_active_requests: 1
  max_queue_size: 2
  max_queue_wait_seconds: 30
  request_timeout_seconds: 120
```

Restart the backend, then run:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario burst_load `
  --poll-queued true `
  --poll-timeout 30
```

Expected actions:

- `soft_pressure`: `max_tokens` may be reduced.
- `high_pressure`: batch requests may be rejected.
- `critical_pressure`: standard traffic may be rejected.
- high-priority traffic should be preserved when possible.

Batch rejection check:

```powershell
$body = @{
  user_id = "user_batch_01"
  project_id = "batch_project"
  model = "simulated-small"
  prompt = "batch request under pressure"
  max_tokens = 64
  request_type = "batch"
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

VIP preservation check:

```powershell
$body = @{
  user_id = "user_vip_01"
  project_id = "vip_project"
  model = "simulated-small"
  prompt = "vip request under pressure"
  max_tokens = 64
  request_type = "interactive"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/generate" `
  -ContentType "application/json" `
  -Body $body
```

After testing, restore `config/limits.yaml`.

## G. Simulated vs Ollama Comparison

Simulated backend behavior is artificial and predictable. Ollama behavior depends on local model inference, hardware, memory, and Ollama runtime behavior.

Enable Ollama manually in `config/models.yaml`:

```yaml
ollama-llama:
  backend: "ollama"
  enabled: true
  ollama_model: "llama3.1"
  ollama_base_url: "http://localhost:11434"
```

Ensure Ollama is installed, running, and has the model:

```powershell
ollama pull llama3.1
ollama list
```

Restart the backend after enabling the model.

Run simulated baseline:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario normal_load `
  --poll-queued true `
  --poll-timeout 30
```

Run Ollama normal load:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario ollama_normal_load `
  --poll-queued true `
  --poll-timeout 120
```

Run Ollama burst load:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario ollama_burst_load `
  --poll-queued true `
  --poll-timeout 180
```

Interpretation:

- Simulated latency is controlled by config and sleeps.
- Ollama latency is real local inference latency.
- Ollama may show higher P95/P99 latency under concurrency.
- Ollama failures may indicate local server, model, timeout, or resource pressure issues.
- Compare by backend and model in `reports/latest_comparison.md`.

## H. Queue and Async Processing

When capacity exists, `/generate` processes immediately. When active capacity is full but queue capacity exists, `/generate` can return:

```json
{
  "status": "queued",
  "message": "Request queued for background processing"
}
```

Use the returned `request_id` to poll:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/requests/<request_id>"
```

Possible statuses:

- `queued`
- `processing`
- `completed`
- `failed`
- `not_found`

Stress tester polling:

```powershell
python -m stress_tester.load_generator `
  --base-url http://127.0.0.1:8000 `
  --scenario burst_load `
  --poll-queued true `
  --poll-interval 0.2 `
  --poll-timeout 30
```

Polling behavior:

- If a request completes immediately, `final_backend_status` is usually `completed`.
- If a request is queued, the stress tester polls `/requests/{request_id}`.
- If polling exceeds timeout, final status is treated as timed out in the report.

## I. Persistence and Usage Accounting

SQLite usage accounting complements in-memory metrics.

Database location:

```text
data/usage.db
```

Global summary:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/usage/summary"
```

Project summary:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/usage/project/standard_project"
```

User summary:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/usage/user/user_standard_01"
```

Recent records:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/usage/recent?limit=20"
```

Use persistence to inspect:

- completed requests
- queued requests
- rejected requests
- failed requests
- token totals
- estimated costs
- backend distribution
- model distribution
- degradation level recorded with requests

Important distinction:

- `/metrics` resets on server restart.
- `data/usage.db` remains after server restart.

## J. Metrics and Reports

Metrics endpoint:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/metrics"
```

Reset metrics:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/metrics/reset"
```

Stress tester reports:

```text
reports/latest_results.csv
reports/latest_summary.json
reports/latest_comparison.md
```

Use `latest_results.csv` for per-request analysis:

- user
- project
- model
- backend
- HTTP status
- initial backend status
- final backend status
- initial latency
- end-to-end latency
- polling attempts
- polling error

Use `latest_summary.json` for aggregate analysis:

- status distributions
- latency percentiles
- final status distributions
- backend/model grouped latency

Use `latest_comparison.md` for a human-readable comparison between backends and models.

## Experiment Matrix

| Experiment | Scenario | Config changes | Expected behavior | Key metrics | Risk/limitation |
|---|---|---|---|---|---|
| Baseline simulated load | `normal_load` | None | Most requests complete; low queue pressure | completed, P50/P95, usage totals | Simulated latency is artificial |
| Burst traffic | `burst_load` | Optional lower `max_active_requests` | More queueing; possible rejection | queued, rejected, queue size, end-to-end latency | Results depend on current limits |
| VIP protection | `vip_protection` | Optional lower queue/active limits | VIP traffic should perform better under pressure | latency by user, final status by user | Current scheduler is simple |
| Rate limiting | `abusive_user` | Optional lower rate limit in `limits.yaml` | User receives policy rejections after limit | HTTP status distribution, rejected count | Rate limiter is in-memory |
| Quota exhaustion | Manual loop or `normal_load` | Lower project quota in `projects.yaml` | Requests rejected after quota is consumed | usage by project, rejected records | Quota manager is in-memory |
| Degradation pressure | `burst_load` | Lower `max_active_requests` and `max_queue_size` | max tokens reduced; batch/standard traffic rejected by level | degradation level, rejected, degraded count | Requires careful temporary config changes |
| Simulated vs Ollama | `normal_load`, `ollama_normal_load` | Enable `ollama-llama` | Ollama latency reflects real local inference | latency by backend/model, final status | Requires local Ollama and model |
| Ollama burst | `ollama_burst_load` | Enable `ollama-llama` | Higher latency or failures under local inference pressure | P95/P99, failed, timed out | Hardware-dependent |
| Long prompt Ollama | `ollama_long_prompt` | Enable `ollama-llama` | Higher end-to-end latency than short prompts | latency by model/backend, failures | May hit local timeout or memory limits |
| Persistence check | Any scenario | None | Usage remains after restart | `/usage/summary`, recent records | SQLite is local only |

## Recommended Testing Order

1. simulated normal load
2. simulated burst load
3. VIP protection
4. abusive user / rate limiting
5. quota exhaustion
6. degradation pressure
7. simulated vs Ollama comparison
8. long prompt Ollama scenario

This order starts with predictable simulated behavior, then increases pressure, then tests governance, then compares real local inference.

## How to Interpret Results

Initial latency:

- Time to receive the first `/generate` response.
- For immediate completions, this includes simulated or real backend processing.
- For queued requests, this is only the time to accept and enqueue the request.

End-to-end latency:

- Time from request submission until final completion, failure, rejection, or polling timeout.
- This is the more important latency for queued requests.

Queue wait time:

- Time spent waiting before background worker processing begins.
- High queue wait means admission and queueing are protecting the backend, but user-visible completion time is increasing.

P50/P95/P99:

- P50 is median behavior.
- P95 shows tail latency for slower requests.
- P99 highlights worst-case behavior and saturation effects.
- Under burst or Ollama load, P95/P99 are often more useful than average latency.

Rejected vs failed:

- `rejected` means the system intentionally refused the request because of policy, quota, degradation, or capacity.
- `failed` means a request was accepted or queued but failed during processing.

Queued vs completed:

- `queued` is not final success. It means the system accepted the request for later processing.
- `completed` means processing finished successfully.
- Use polling or `/requests/{request_id}` to check queued requests.

Backend/model comparison:

- Use `requests_by_backend`, `latency_by_backend`, and `end_to_end_latency_by_backend` to compare simulated vs Ollama.
- Use model-level metrics to compare `simulated-small`, `simulated-large`, and `ollama-llama`.
- Simulated and Ollama results answer different questions: simulated tests architecture behavior; Ollama tests local inference behavior.

## Known Limitations

- Queue state is in-memory.
- Metrics are in-memory.
- SQLite is local only.
- No distributed workers.
- No authentication on admin, metrics, or usage endpoints.
- No streaming yet.
- No Redis, Celery, Kafka, Prometheus, or Grafana integration.
- Rate limiting and quota state are currently in-memory.
- Ollama performance depends on local CPU, GPU, RAM, model size, and Ollama configuration.
- Stress tests run from one local process and are not distributed load tests.
