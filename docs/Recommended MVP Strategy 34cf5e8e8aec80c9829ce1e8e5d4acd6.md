# Recommended MVP Strategy


# MVP Goal

Validate the architecture under load before deploying it on a real server.

The MVP should answer:

1. Can the backend survive thousands of requests?
2. Do queues behave correctly?
3. Do VIP projects get better service?
4. Are token quotas enforced?
5. Are costs tracked per user/project?
6. What happens when the system is saturated?
7. Is Ollama the bottleneck, or is our control layer the bottleneck?

---

# Recommended MVP Strategy

## Phase 1 — Simulated LLM Backend

**Most suitable first step.**

Instead of calling Ollama immediately, we simulate the model with artificial delays.

Example simulation logic:

```
Short prompt  -> 0.5s delay
Medium prompt -> 2s delay
Long prompt   -> 5s delay
VIP request   -> higher priority
Batch request -> lower priority
```

### Why this comes first

Because it lets us validate the architecture without mixing two problems:

- our backend design,
- Ollama performance limits.

### What we validate

- API capacity,
- queue behavior,
- priority scheduling,
- rate limiting,
- quota control,
- cost accounting,
- rejection policies,
- latency under stress.

### Final consideration

This phase gives clean results because the “LLM” is predictable.

---

## Phase 2 — Local Ollama Integration

After the simulation works, we replace the fake backend with Ollama.

Ollama exposes local API endpoints such as `/api/generate` and `/api/chat`, and streaming can be enabled or disabled depending on the request mode. Ollama also has concurrency-related settings; its FAQ notes that parallel requests increase memory allocation because context is effectively multiplied by the number of parallel requests. ([Ollama Docs](https://docs.ollama.com/faq?utm_source=chatgpt.com))

### Why this comes second

Because now we can compare:

```
Simulated backend performance
vs
Real Ollama backend performance
```

That tells us where the bottleneck is.

### What we validate

- real inference latency,
- Ollama concurrency limits,
- memory pressure,
- token generation speed,
- streaming behavior,
- timeout behavior,
- practical capacity of the local machine.

### Final consideration

Ollama is excellent for local experimentation, but for high-concurrency production serving, the architecture should keep the LLM backend replaceable.

---

## Phase 3 — Stress Testing App

Build a separate Python app whose only purpose is to attack/test the backend.

This stress app should simulate:

- 10 users,
- 100 users,
- 1,000 users,
- VIP projects,
- standard projects,
- abusive users,
- batch jobs,
- long prompts,
- short prompts,
- sudden traffic bursts.

### Why it is necessary

Because the backend cannot be validated with manual requests.

### What it should measure

- requests completed,
- requests rejected,
- requests queued,
- average latency,
- P95 latency,
- P99 latency,
- queue waiting time,
- tokens consumed,
- estimated cost,
- VIP vs standard performance.

---

# Proposed MVP Components

```
llm-load-mvp/
│
├── backend/
│   ├── api_server
│   ├── request_validator
│   ├── policy_engine
│   ├── rate_limiter
│   ├── quota_manager
│   ├── cost_tracker
│   ├── admission_controller
│   ├── priority_scheduler
│   ├── queue_manager
│   ├── llm_backend
│   │   ├── simulated_backend
│   │   └── ollama_backend
│   └── metrics
│
├── stress_tester/
│   ├── load_generator
│   ├── scenarios
│   └── reports
│
└── config/
    ├── users.yaml
    ├── projects.yaml
    ├── limits.yaml
    └── models.yaml
```

---

# MVP Features Ranked by Priority

## 1. Admission Controller

**Highest priority.**

Decides whether a request is:

```
accepted
queued
degraded
rejected
```

### Why first

This is the main protection mechanism.

---

## 2. Priority Queue

Required to test VIP behavior.

Example:

```
VIP interactive       -> highest priority
Standard interactive  -> normal priority
Batch                 -> low priority
```

### Why second

Without this, all requests are treated equally and we cannot validate service levels.

---

## 3. Rate Limiter

Controls request frequency.

Example:

```
standard_user: 30 requests/min
vip_user: 300 requests/min
batch_user: 10 requests/min
```

### Why third

It prevents abusive traffic.

---

## 4. Token Quota Manager

Controls token consumption.

Example:

```
standard_project: 1M tokens/month
vip_project: 20M tokens/month
internal_admin: unlimited
```

### Why fourth

This validates governance and cost control.

---

## 5. Cost Tracker

Tracks estimated cost.

Example:

```
request_cost = input_tokens * input_price + output_tokens * output_price
```

### Why fifth

Important for real service operation, even if approximate in the MVP.

---

## 6. Simulated LLM Worker Pool

Processes fake model requests with configurable delay.

### Why sixth

Allows repeatable performance testing.

---

## 7. Ollama Backend Adapter

Connects the same architecture to local Ollama.

### Why seventh

Important, but better after the simulation backend works.

---

## 8. Metrics and Reports

Needed to evaluate results.

Minimum metrics:

```
total requests
accepted requests
queued requests
rejected requests
average latency
P95 latency
P99 latency
tokens consumed
cost per project
VIP latency vs standard latency
```

---

# Recommended Technology Stack

## Backend

```
Python + FastAPI
```

Why:

- simple API development,
- async support,
- good for simulation,
- easy integration with Ollama.

## Async engine

```
asyncio
```

Why:

- suitable for thousands of concurrent simulated requests,
- good for queues and workers.

## HTTP client

```
httpx
```

Why:

- async requests,
- works well for stress testing and Ollama calls.

## Configuration

```
YAML or JSON
```

Why:

- easy to define users, projects, limits and model costs.

## Metrics

For MVP:

```
in-memory metrics + CSV export
```

Later:

```
Prometheus + Grafana
```

## Storage

For MVP:

```
SQLite or in-memory
```

Later:

```
PostgreSQL
```

---

# MVP Execution Flow

```
1. Client sends request
2. Backend validates request
3. Policy engine checks user/project/model
4. Rate limiter checks request frequency
5. Quota manager checks remaining tokens
6. Cost tracker estimates cost
7. Admission controller decides accept/queue/reject/degrade
8. Scheduler selects next request
9. Simulated backend or Ollama processes request
10. Metrics are recorded
11. Response is returned
```

---

# Stress Testing Scenarios

## Scenario 1 — Normal Load

```
100 users
short prompts
standard projects
```

Expected result:

```
low latency
no rejections
stable queue
```

---

## Scenario 2 — Burst Load

```
1,000 requests in 10 seconds
mixed users
```

Expected result:

```
queue grows temporarily
some low-priority traffic delayed
system remains alive
```

---

## Scenario 3 — VIP Protection

```
standard users flood the system
VIP user sends requests during overload
```

Expected result:

```
VIP latency remains lower
standard users may wait
batch jobs delayed
```

---

## Scenario 4 — Token Quota Exhaustion

```
project consumes its daily token quota
```

Expected result:

```
new requests rejected or degraded
clear quota message returned
```

---

## Scenario 5 — Abusive User

```
one user sends 500 requests/min
```

Expected result:

```
rate limiter blocks/throttles abusive user
other users remain unaffected
```

---

## Scenario 6 — Ollama Real Backend

```
same scenarios
but using local Ollama
```

Expected result:

```
measure real model bottlenecks
compare against simulation baseline
```

---

# Implementation Order

## Step 1 — Define config files

Users, projects, limits, model costs.

## Step 2 — Build backend skeleton

FastAPI endpoints and request schema.

## Step 3 — Add simulated LLM backend

Fake latency and fake token usage.

## Step 4 — Add policy engine

Rate limits, quotas, VIP status.

## Step 5 — Add admission controller and queues

Bounded priority queues.

## Step 6 — Add metrics

Latency, queue time, rejection rate, cost.

## Step 7 — Build stress tester

Async Python script generating thousands of requests.

## Step 8 — Add Ollama adapter

Use Ollama as a real local backend.

## Step 9 — Compare results

Simulation vs Ollama.

---

# Minimal MVP Scope

To avoid overbuilding, the first MVP should include only:

```
FastAPI backend
Simulated LLM backend
Priority queue
Rate limiter
Quota manager
Cost tracker
Stress tester
CSV report
```

Then second MVP:

```
Ollama backend adapter
Streaming support
Prometheus metrics
SQLite/PostgreSQL persistence
```

---

# Final Recommendation

The best implementation strategy is:

## 1. Build a simulation-first backend

Most appropriate because it validates the architecture cleanly.

## 2. Add stress testing tool

Necessary to reproduce thousands of requests.

## 3. Add Ollama integration

Useful for realistic local testing.

## 4. Compare simulated vs real backend

This tells us whether the bottleneck is architectural or caused by local inference.

So the MVP should not be “an app that calls Ollama directly”.

It should be:

```
A Python control layer around an LLM backend,
with simulation mode first and Ollama mode second.
```

That will let you validate the real value of the design before moving to a production server.