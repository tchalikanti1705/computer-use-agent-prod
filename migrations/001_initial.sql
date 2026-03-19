CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
    api_key TEXT NOT NULL UNIQUE, config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_tenants_api_key ON tenants(api_key);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    instruction TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
    config JSONB NOT NULL DEFAULT '{}', result TEXT, error TEXT,
    total_steps INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ);
CREATE INDEX IF NOT EXISTS idx_tasks_tenant ON tasks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS action_logs (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
    step_number INTEGER NOT NULL, action_type TEXT NOT NULL,
    action_payload JSONB NOT NULL DEFAULT '{}', screenshot_key TEXT,
    tokens_used INTEGER DEFAULT 0, safety_approved BOOLEAN DEFAULT true,
    safety_reason TEXT, duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_actions_session ON action_logs(session_id);

CREATE TABLE IF NOT EXISTS usage_records (
    id SERIAL PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    session_id TEXT NOT NULL, tokens_used INTEGER DEFAULT 0,
    vm_seconds INTEGER DEFAULT 0, actions_count INTEGER DEFAULT 0,
    screenshots INTEGER DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS idx_usage_tenant ON usage_records(tenant_id);
