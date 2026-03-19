# Computer User Agent — Setup & Run Guide

## Prerequisites

- **Docker Desktop** (with Docker Compose v2)
- **Python 3.12+**
- **OpenAI API key** (with computer-use / responses API access)
- ~4GB free RAM (for Postgres + Redis + MinIO + sandbox VMs)

---

## Step 1: Unzip and Setup

```bash
# Unzip the project
unzip computer-user-agent-prod.zip
cd computer-user-agent-prod

# Create your .env file
cp .env.example .env
```

Edit `.env` — the only **required** change:
```
OPENAI_API_KEY=sk-your-real-openai-key-here
```

Optional (if you also want Anthropic fallback):
```
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
```

---

## Step 2: Build the Sandbox Image

This is the Ubuntu VM that agents control:

```bash
cd sandbox
docker build -t cua-sandbox:latest .
cd ..
```

**Expected output:**
```
[+] Building 120.5s
 => => naming to docker.io/library/cua-sandbox:latest
```

---

## Step 3: Start Infrastructure

```bash
docker compose up -d postgres redis minio
```

**Expected output:**
```
[+] Running 3/3
 ✔ Container computer-user-agent-prod-postgres-1  Started
 ✔ Container computer-user-agent-prod-redis-1     Started
 ✔ Container computer-user-agent-prod-minio-1     Started
```

Wait 5 seconds for them to be healthy:
```bash
docker compose ps
```
```
NAME       SERVICE    STATUS
...postgres-1   postgres   running (healthy)
...redis-1      redis      running (healthy)
...minio-1      minio      running
```

---

## Step 4: Run Database Migrations

```bash
pip install -r requirements.txt
python -m scripts.migrate
```

**Expected output:**
```
Running: 001_initial.sql
  Done: 001_initial.sql
Done.
```

---

## Step 5: Start the Gateway API

Open a new terminal:
```bash
cd computer-user-agent-prod
uvicorn gateway.app:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     gateway_starting
```

---

## Step 6: Start the Control Plane (Scheduler)

Open another terminal:
```bash
cd computer-user-agent-prod
uvicorn control_plane.app:app --reload --port 8001
```

**Expected output:**
```
INFO:     control_plane_started
INFO:     scheduler_started
```

---

## Step 7: Start the Agent Worker

Open another terminal:
```bash
cd computer-user-agent-prod
python -m agent_runtime.worker
```

**Expected output:**
```
worker_started
```
(Worker now blocks, waiting for tasks from the queue)

---

## Step 8: Use the API — Full Example

### 8a. Health Check

```bash
curl http://localhost:8000/health
```

**Output:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### 8b. Create a Tenant

```bash
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "acme-corp",
    "email": "admin@acme.com",
    "allowed_domains": ["google.com", "wikipedia.org", "weather.com"],
    "max_concurrent_sessions": 3,
    "llm_provider": "openai",
    "llm_model": "gpt-4o"
  }'
```

**Output:**
```json
{
  "id": "a1b2c3d4-5678-9abc-def0-1234567890ab",
  "name": "acme-corp",
  "email": "admin@acme.com",
  "api_key": "cua_8f3a1b2c4d5e6f7a8b9c0d1e2f3a4b5c",
  "is_active": true
}
```

> **Save the `api_key`** — you'll use it for all subsequent requests.

---

### 8c. Submit a Task

```bash
# Replace <API_KEY> with the api_key from step 8b
export API_KEY="cua_8f3a1b2c4d5e6f7a8b9c0d1e2f3a4b5c"

curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Open Firefox and go to google.com. Search for weather in New York City. Tell me the temperature.",
    "timeout_seconds": 300,
    "require_human_approval": false
  }'
```

**Output:**
```json
{
  "id": "f7e6d5c4-b3a2-1098-7654-fedcba987654",
  "tenant_id": "a1b2c3d4-5678-9abc-def0-1234567890ab",
  "status": "pending",
  "instruction": "Open Firefox and go to google.com...",
  "created_at": "2026-03-19T02:30:00.000000"
}
```

> Save the task `id` to check status later.

---

### 8d. What Happens Behind the Scenes

Once you submit the task, here's the flow through the architecture:

```
1. Gateway receives request
     → Validates API key (Auth Service)
     → Checks rate limit (60 req/min per tenant)
     → Checks concurrent session limit (max 3)
     → Stores task in PostgreSQL
     → Pushes to Redis task queue

2. Control Plane scheduler picks it up
     → Dequeues from Redis
     → Looks up tenant config (allowed domains, LLM preference)
     → Pushes assignment to worker queue

3. Agent Worker receives assignment
     → Spins up fresh Docker sandbox (Ubuntu + Firefox)
     → Creates session in Redis
     → Starts Agent Loop:

     Step 0: Capture screenshot of fresh desktop
             → Send to OpenAI: "Here's what I see + user instruction"
             → OpenAI returns: click(x=640, y=400) to open Firefox

     Step 1: Safety Layer validates: click action → APPROVED
             → VM Controller executes: xdotool mousemove 640 400 click 1
             → Capture new screenshot → Store in S3
             → Send to OpenAI with new screenshot

     Step 2: OpenAI returns: click address bar, type "google.com"
             → Safety Layer: URL check → google.com is in allowlist → APPROVED
             → Execute, capture screenshot

     Step 3: OpenAI returns: type "weather in New York City", press Enter
             → Safety Layer: text check → no risky keywords → APPROVED
             → Execute, capture screenshot

     Step 4: OpenAI reads the search results screenshot
             → Returns message: "The temperature in NYC is 45°F"
             → No more computer_call → TASK COMPLETE

4. Worker updates task status in PostgreSQL
     → Records billing: 4 steps, ~2000 tokens, 45 VM-seconds
     → Destroys sandbox container
     → Cleans up session
```

**Worker terminal shows:**
```
worker_task_received    task_id=f7e6d5c4... tenant_id=a1b2c3d4...
sandbox_created         session_id=... container=cua-a1b2c3d4-e5f6a7b8
agent_loop_start        task_id=f7e6d5c4... instruction=Open Firefox...
model_msg               step=0 msg=I'll open Firefox and navigate to Google...
model_msg               step=2 msg=Now I'll search for weather in NYC...
model_msg               step=4 msg=The temperature in New York City is 45°F
agent_loop_complete     task_id=f7e6d5c4... steps=4
task_complete           task_id=f7e6d5c4... status=completed steps=4
sandbox_destroyed       session_id=...
```

---

### 8e. Check Task Status

```bash
export TASK_ID="f7e6d5c4-b3a2-1098-7654-fedcba987654"

curl http://localhost:8000/api/v1/tasks/$TASK_ID \
  -H "Authorization: Bearer $API_KEY"
```

**Output (while running):**
```json
{
  "id": "f7e6d5c4-b3a2-1098-7654-fedcba987654",
  "status": "running",
  "total_steps": 2,
  "total_tokens": 1200,
  "result": null,
  "error": null
}
```

**Output (after completion):**
```json
{
  "id": "f7e6d5c4-b3a2-1098-7654-fedcba987654",
  "status": "completed",
  "total_steps": 4,
  "total_tokens": 2150,
  "result": "[\"I'll open Firefox and navigate to Google.\", \"The temperature in New York City is currently 45°F (7°C) with partly cloudy skies.\"]",
  "error": null
}
```

---

### 8f. WebSocket Live Stream (Real-Time)

Connect to watch the agent work live:

```bash
# Using websocat (brew install websocat / cargo install websocat)
websocat ws://localhost:8000/ws/stream/<session_id>
```

**Live output (streamed as JSON):**
```json
{"type":"status","session_id":"...","data":{"status":"running","message":"Agent started"}}
{"type":"action","session_id":"...","data":{"step":0,"action":{"type":"click","x":640,"y":400},"safety_approved":true}}
{"type":"screenshot","session_id":"...","data":{"step":1,"size":245000}}
{"type":"action","session_id":"...","data":{"step":1,"action":{"type":"type","text":"google.com"},"safety_approved":true}}
{"type":"screenshot","session_id":"...","data":{"step":2,"size":312000}}
{"type":"status","session_id":"...","data":{"status":"completed","message":""}}
```

---

## Example: Safety Layer Blocking an Action

Submit a task that tries to access a blocked domain:

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Go to malicious-site.com and download the file"
  }'
```

**Worker terminal shows:**
```
agent_loop_start        instruction=Go to malicious-site.com...
safety_blocked          step=1 reason=Domain not allowed: malicious-site.com
task_complete           status=failed
sandbox_destroyed
```

**Task status output:**
```json
{
  "id": "...",
  "status": "failed",
  "total_steps": 1,
  "total_tokens": 800,
  "result": null,
  "error": "Domain not allowed: malicious-site.com"
}
```

---

## Example: Multiple Tenants (Isolation Demo)

```bash
# Create Tenant B with DIFFERENT allowed domains
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "startup-xyz",
    "email": "founder@startup.xyz",
    "allowed_domains": ["github.com", "stackoverflow.com"],
    "max_concurrent_sessions": 2,
    "llm_provider": "openai",
    "llm_model": "gpt-4o"
  }'
```

Now Tenant B can access GitHub but NOT Google. Tenant A can access Google but NOT GitHub. Each gets their own sandbox VM, their own safety policies, their own billing.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

**Expected output:**
```
tests/test_safety.py::test_allowed_url PASSED
tests/test_safety.py::test_blocked_url PASSED
tests/test_safety.py::test_risky_text_strict PASSED
tests/test_safety.py::test_safe_text PASSED
tests/test_safety.py::test_alt_f4_blocked PASSED
tests/test_safety.py::test_normal_key PASSED
tests/test_safety.py::test_batch_too_large PASSED
tests/test_safety.py::test_safe_actions_pass PASSED
tests/test_models.py::test_tenant_creation PASSED
tests/test_models.py::test_task_defaults PASSED

10 passed in 0.3s
```

---

## Quick Reference: All Terminals You Need

| Terminal | Command | Purpose |
|----------|---------|---------|
| 1 | `docker compose up -d postgres redis minio` | Infrastructure |
| 2 | `uvicorn gateway.app:app --reload --port 8000` | API Gateway |
| 3 | `uvicorn control_plane.app:app --reload --port 8001` | Scheduler |
| 4 | `python -m agent_runtime.worker` | Agent Worker |
| 5 | `curl ...` commands | Your API calls |

Or run everything at once with Docker:
```bash
docker compose up -d    # starts all services including workers
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Connection refused" on API calls | Make sure gateway is running on port 8000 |
| "Task stays pending" | Check that control plane + worker are both running |
| "Sandbox failed to start" | Run `docker build -t cua-sandbox:latest sandbox/` first |
| "Invalid API key" | Use the full `cua_...` key from tenant creation response |
| Worker crashes with Docker error | Make sure Docker socket is accessible (`/var/run/docker.sock`) |
