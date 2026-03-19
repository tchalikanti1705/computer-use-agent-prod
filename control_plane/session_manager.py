from datetime import datetime
from shared.redis_client import SessionState
from shared.config import get_settings
import structlog
logger = structlog.get_logger()

class SessionManager:
    def __init__(self):
        self.state = SessionState()
        self.settings = get_settings()
    def create_session(self, sid, tenant_id, task_id, container_id=None):
        data = {"session_id": sid, "tenant_id": tenant_id, "task_id": task_id,
                "container_id": container_id, "status": "active",
                "created_at": datetime.utcnow().isoformat()}
        self.state.set_session(sid, data, ttl=self.settings.vm_max_lifetime_seconds)
        return data
    def update_activity(self, sid):
        s = self.state.get_session(sid)
        if s:
            s["last_activity"] = datetime.utcnow().isoformat()
            self.state.set_session(sid, s, ttl=self.settings.vm_max_lifetime_seconds)
    def end_session(self, sid):
        self.state.delete_session(sid)
