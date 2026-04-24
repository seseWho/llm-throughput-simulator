# Logical Architecture

# 1. Architecture Goal

Design a server-side platform able to manage thousands of LLM requests while controlling:

- performance,
- queues,
- token consumption,
- cost,
- user/project quotas,
- VIP prioritization,
- fairness,
- degradation under load.

---

# 2. Recommended Logical Architecture

```
Clients / Apps / Batch Jobs
        |
        v
API Gateway
        |
        v
Authentication & Request Validation
        |
        v
Policy Layer
Rate Limiter + Quota Manager + Cost Estimator
        |
        v
Admission Controller
        |
        v
Priority Scheduler
        |
        v
Queue System
Interactive Queue | VIP Queue | Batch Queue
        |
        v
Inference Orchestrator
        |
        v
LLM Serving Backend
vLLM / TGI / Triton / Custom Engine
        |
        v
Response Manager
Streaming / Sync / Async
        |
        v
Client
```

Parallel to all components:

```
Observability Layer
Metrics | Logs | Traces | Alerts | Dashboards
```

And for governance:

```
Governance Database
Users | Projects | Quotas | Budgets | Policies | Usage History
```

---

# 3. Components Ordered by Importance

## 1. API Gateway

**Role**

Entry point for all requests.

**Responsibilities**

- Receive API calls.
- Normalize request format.
- Apply basic request size limits.
- Route traffic to the internal service.

**Why it is first**

It isolates clients from the internal architecture and becomes the first control point.

**Final consideration**

The gateway should not contain complex LLM logic. It should remain lightweight.

---

## 2. Authentication and Request Validation

**Role**

Identify who is making the request and whether the request is valid.

**Responsibilities**

- Validate API key or token.
- Identify user and project.
- Validate model name, input size, endpoint and request type.
- Reject malformed requests early.

**Why it is second**

No governance is possible if the system does not know who is consuming resources.

**Final consideration**

Every request should carry metadata: `user_id`, `project_id`, `priority`, `model`, `request_type`.

---

## 3. Policy Layer

This is one of the most important parts of the architecture.

It includes:

```
Rate Limiter
Quota Manager
Cost Estimator
Budget Controller
Priority Resolver
```

### 3.1 Rate Limiter

**Purpose**

- Limit requests per second/minute/hour.

**Examples**

- Standard user: 60 requests/min.
- VIP project: 500 requests/min.
- Batch job: 10 requests/min but higher queue tolerance.

### 3.2 Quota Manager

**Purpose**

- Control token and request caps.

**Examples**

- User A: 1 million tokens/month.
- Project X: 50 million tokens/month.
- VIP Project: 200 million tokens/month.

### 3.3 Cost Estimator

**Purpose**

- Estimate cost before and after execution.

**Tracks**

- Input tokens.
- Output tokens.
- Model price.
- Cost per user.
- Cost per project.

### 3.4 Budget Controller

**Purpose**

- Prevent uncontrolled spending.

**Possible rules**

- At 80% budget: alert.
- At 90% budget: throttle.
- At 100% budget: block or downgrade.

### 3.5 Priority Resolver

**Purpose**

- Decide the effective priority of a request.

**Example**

A request may be VIP because:

- project is VIP,
- endpoint is critical,
- user has elevated access,
- job is marked as production-critical.

**Why this layer is third**

It decides whether a request deserves resources before the system spends expensive compute.

**Final consideration**

This layer should be configurable without redeploying the system.

---

## 4. Admission Controller

**Role**

Decide whether a request enters the system now, waits, is degraded, or is rejected.

**Possible decisions**

- Accept immediately.
- Put into queue.
- Route to cheaper model.
- Reduce max output tokens.
- Reject with a clear error.
- Convert to asynchronous job.

**Why it is critical**

This component protects the service from collapse.

**Example**

If GPU capacity is saturated and queue length is above threshold:

```
VIP interactive request     -> accept
Standard interactive request -> queue
Batch request               -> defer
Abusive request             -> reject
```

**Final consideration**

This is the heart of system stability.

---

## 5. Priority Scheduler

**Role**

Choose which queued request is executed next.

**Possible strategies**

- FIFO.
- Priority queue.
- Weighted fair queue.
- Round-robin by project.
- Deadline-aware scheduling.
- Token-aware scheduling.

**Recommended strategy**

Use **weighted fair scheduling**:

```
VIP projects      -> higher weight
Standard projects -> normal weight
Batch jobs        -> lower weight
```

This prevents VIP starvation and also avoids completely starving normal users.

**Final consideration**

A simple FIFO queue is usually not enough for production LLM serving.

---

## 6. Queue System

**Role**

Store pending requests safely and predictably.

**Recommended queues**

- VIP interactive queue.
- Standard interactive queue.
- Batch queue.
- Retry/deferred queue.

**Queue policies**

- Maximum queue size.
- Maximum waiting time.
- Per-priority queue limits.
- Expiration of old requests.
- Cancellation support.

**Why it matters**

The queue absorbs peaks, but if it is unbounded, it becomes dangerous.

**Final consideration**

A bounded queue is better than an infinite queue. Infinite queues hide failure until it is too late.

---

## 7. Inference Orchestrator

**Role**

Coordinate execution against the LLM backend.

**Responsibilities**

- Select model.
- Select backend instance.
- Apply runtime parameters.
- Track request lifecycle.
- Support cancellation.
- Send results to response manager.
- Collect token usage.

**Model routing examples**

- Small task → small model.
- VIP task → best available model.
- High load → faster model.
- Batch task → lower-priority backend.

**Final consideration**

This component should not implement the model itself. It orchestrates serving.

---

## 8. LLM Serving Backend

**Role**

Actually run inference.

**Possible backends**

- vLLM.
- Text Generation Inference.
- Triton.
- Ollama/LM Studio for local experiments.
- Custom Python backend for the PoC.

**Capabilities to consider**

- Continuous batching.
- Streaming.
- KV cache.
- Prefix caching.
- Multi-GPU support.
- Model quantization.
- Tensor parallelism.

**Final consideration**

For the PoC, this can be simulated. For production, this becomes a major performance decision.

---

## 9. Response Manager

**Role**

Deliver the response according to the request type.

**Modes**

- Synchronous response.
- Streaming response.
- Asynchronous job result.
- Deferred result.

**Responsibilities**

- Stream tokens when available.
- Notify completion.
- Handle client disconnect.
- Return queue status.
- Return clear rejection messages.

**Final consideration**

This component strongly affects perceived usability.

---

## 10. Governance Database

**Role**

Store configuration and usage records.

**Stores**

- Users.
- Projects.
- API keys.
- Plans.
- Quotas.
- Budgets.
- Token usage.
- Cost history.
- Priority policies.
- Audit logs.

**Example entities**

```
User
- user_id
- project_id
- role
- status

Project
- project_id
- plan
- monthly_token_quota
- monthly_budget
- priority_level

UsageRecord
- request_id
- user_id
- project_id
- model
- input_tokens
- output_tokens
- estimated_cost
- latency
- status
```

**Final consideration**

This is essential for cost control and future reporting.

---

## 11. Observability Layer

**Role**

Make the system measurable and controllable.

**Metrics**

- Requests per second.
- Tokens per second.
- Queue length.
- Queue waiting time.
- Latency P50/P95/P99.
- Cost per project.
- Error rate.
- Rejection rate.
- GPU utilization.
- Model utilization.

**Logs**

- Request accepted.
- Request queued.
- Request rejected.
- Request degraded.
- Request completed.
- Request failed.

**Traces**

- Gateway time.
- Policy check time.
- Queue wait time.
- Inference time.
- Response streaming time.

**Final consideration**

Without observability, the system cannot be tuned safely.

---

# 4. Request Lifecycle

## Step 1. Request arrives

Client sends:

```json
{
  "user_id": "u123",
  "project_id": "project_vip_01",
  "model": "llama-70b",
  "prompt": "...",
  "max_tokens": 500,
  "request_type": "interactive"
}
```

---

## Step 2. Validation

The system checks:

- Is the API key valid?
- Is the model allowed?
- Is the prompt too large?
- Is the project active?
- Is the user allowed to use this endpoint?

---

## Step 3. Policy evaluation

The system checks:

- current rate limit,
- remaining token quota,
- remaining budget,
- project priority,
- current system load.

---

## Step 4. Admission decision

Possible outcomes:

```
ACCEPT
QUEUE
DEGRADE
REJECT
ASYNC
```

---

## Step 5. Scheduling

The scheduler chooses the next request according to:

- priority,
- fairness,
- queue age,
- token estimate,
- project weight.

---

## Step 6. Inference

The orchestrator sends the request to the selected LLM backend.

---

## Step 7. Response

Response manager returns:

- streaming tokens,
- final response,
- job status,
- error,
- or retry recommendation.

---

## Step 8. Accounting

The system records:

- input tokens,
- output tokens,
- total cost,
- latency,
- queue time,
- status,
- user/project usage.

---

# 5. Degradation Strategy

When load increases, the system should not fail suddenly.

## Recommended degradation levels

### Level 0 — Normal

```
All requests accepted normally.
```

### Level 1 — Soft pressure

```
Batch requests delayed.
Max tokens reduced slightly.
```

### Level 2 — High pressure

```
Standard requests queued.
VIP requests prioritized.
Batch requests paused.
```

### Level 3 — Critical pressure

```
Only VIP and critical interactive requests accepted.
Standard traffic degraded or rejected.
```

### Level 4 — Emergency

```
Reject most new requests.
Preserve health of the system.
```

---

# 6. Architecture Decisions Ranked

## 1. Admission Controller

**Most important.**

Prevents overload and protects user experience.

## 2. Policy Layer

Controls cost, quota, rate limits and VIP access.

## 3. Priority Scheduler

Ensures fair and intelligent execution.

## 4. Queue System

Absorbs peaks safely.

## 5. Inference Orchestrator

Connects system policies to actual model execution.

## 6. Observability Layer

Allows tuning, debugging and production monitoring.

## 7. LLM Backend

Critical for performance, but replaceable if the architecture is clean.

## 8. Response Manager

Improves usability through streaming, async and clear status.

---

# 7. Minimal PoC Architecture Later

For the future simulation, the first PoC should implement only:

```
FastAPI Server
    |
Request Validator
    |
Policy Layer
    |
Admission Controller
    |
Priority Queue
    |
Simulated LLM Worker Pool
    |
Metrics Dashboard / Logs
```

The LLM can be simulated first using artificial delays and token counts.

That allows testing:

- thousands of requests,
- queue behavior,
- VIP priority,
- token quotas,
- rate limits,
- rejection policy,
- latency distribution,
- cost accounting.

---

# Final Recommendation

The best architecture is not just an LLM server. It is a **controlled resource-management platform around an LLM backend**.

The core idea is:

```
Do not let requests go directly to the model.
Every request must pass through policy, admission, scheduling and accounting.
```

That is what makes the system scalable, fair and production-ready.