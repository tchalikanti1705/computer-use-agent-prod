from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from shared.config import get_settings
import json, structlog
logger = structlog.get_logger()

def get_engine():
    return create_engine(get_settings().database_url, pool_size=20, max_overflow=10)

def get_db_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

class TenantStore:
    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def create_tenant(self, data: dict) -> dict:
        with self.engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO tenants (id,name,email,api_key,config,is_active,created_at) "
                "VALUES (:id,:name,:email,:api_key,:config,true,NOW())"
            ), {"id": data["id"], "name": data["name"], "email": data["email"],
                "api_key": data["api_key"],
                "config": json.dumps({k: data.get(k) for k in
                    ["allowed_domains","max_concurrent_sessions","llm_provider","llm_model"]})})
            conn.commit()
        return data

    def get_tenant_by_api_key(self, api_key: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM tenants WHERE api_key=:k AND is_active=true"),
                               {"k": api_key}).mappings().fetchone()
            if row:
                r = dict(row)
                r["config"] = json.loads(r["config"]) if isinstance(r["config"], str) else r["config"]
                return r
        return None

    def get_tenant(self, tid: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM tenants WHERE id=:id"), {"id": tid}).mappings().fetchone()
            if row:
                r = dict(row)
                r["config"] = json.loads(r["config"]) if isinstance(r["config"], str) else r["config"]
                return r
        return None

class TaskStore:
    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def create_task(self, data: dict) -> dict:
        with self.engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO tasks (id,tenant_id,instruction,status,config,created_at) "
                "VALUES (:id,:tid,:instr,:status,:config,NOW())"
            ), {"id": data["id"], "tid": data["tenant_id"], "instr": data["instruction"],
                "status": "pending", "config": json.dumps({
                    "callback_url": data.get("callback_url"),
                    "timeout_seconds": data.get("timeout_seconds", 600),
                    "require_human_approval": data.get("require_human_approval", False)})})
            conn.commit()
        return data

    def update_task_status(self, task_id: str, status: str, **kwargs):
        sets = ["status=:status"]
        params = {"task_id": task_id, "status": status}
        for k, v in kwargs.items():
            sets.append(f"{k}=:{k}")
            params[k] = v
        with self.engine.connect() as conn:
            conn.execute(text(f"UPDATE tasks SET {','.join(sets)} WHERE id=:task_id"), params)
            conn.commit()

    def get_task(self, task_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM tasks WHERE id=:id"), {"id": task_id}).mappings().fetchone()
            return dict(row) if row else None
