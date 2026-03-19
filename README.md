# Computer User Agent — Production Architecture

Multi-tenant SaaS platform for autonomous AI agents that control real desktop environments.

## Architecture layers

1. **Client Layer** — Multi-tenant (Web dashboard, API, CLI/SDK)
2. **Gateway** — API Gateway (FastAPI) + Auth (JWT/API keys) + Rate limiting
3. **Control Plane** — Task Queue (Redis) + Session Manager + Agent Scheduler + Billing
4. **Agent Runtime** — Agent Loop + Safety Layer + VM Controller + LLM Router
5. **VM Pool** — Ephemeral sandboxed Docker containers (Ubuntu + Firefox)
6. **Data Layer** — PostgreSQL + Redis + S3 + Prometheus/Grafana

## Quick Start

```bash
cp .env.example .env
docker compose up -d
python -m scripts.migrate
```

## Run Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

## API

```bash
# Create tenant
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "acme", "email": "admin@acme.com"}'

# Submit task
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Go to google.com and search for weather"}'

# Check status
curl http://localhost:8000/api/v1/tasks/<task_id> \
  -H "Authorization: Bearer <api_key>"
```

## Key Design Decisions

- **Tenant isolation**: Dedicated agent instances + network-isolated VMs per tenant
- **Safety as infrastructure**: Every action passes through per-tenant policy engine
- **Ephemeral VMs**: Fresh container per session, destroyed on completion
- **LLM-agnostic**: Swap OpenAI/Anthropic per tenant with automatic fallback
- **Audit trail**: Every action + screenshot stored in S3
- **Human-in-the-loop**: Configurable escalation via WebSocket
