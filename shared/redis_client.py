import json, redis
from shared.config import get_settings
import structlog
logger = structlog.get_logger()

def get_redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)

class TaskQueue:
    QUEUE_KEY = "agent:task_queue"
    PROCESSING_KEY = "agent:processing"
    def __init__(self, r=None):
        self.r = r or get_redis()
    def enqueue(self, task_id: str, tenant_id: str, priority: int = 0):
        self.r.zadd(self.QUEUE_KEY, {json.dumps({"task_id": task_id, "tenant_id": tenant_id}): priority})
    def dequeue(self) -> dict | None:
        items = self.r.zpopmin(self.QUEUE_KEY, count=1)
        if not items: return None
        payload, _ = items[0]
        data = json.loads(payload)
        self.r.sadd(self.PROCESSING_KEY, data["task_id"])
        return data
    def mark_done(self, task_id: str):
        self.r.srem(self.PROCESSING_KEY, task_id)
    def queue_length(self) -> int:
        return self.r.zcard(self.QUEUE_KEY)

class SessionState:
    PREFIX = "agent:session:"
    def __init__(self, r=None):
        self.r = r or get_redis()
    def set_session(self, sid: str, data: dict, ttl: int = 1800):
        self.r.setex(f"{self.PREFIX}{sid}", ttl, json.dumps(data))
    def get_session(self, sid: str) -> dict | None:
        raw = self.r.get(f"{self.PREFIX}{sid}")
        return json.loads(raw) if raw else None
    def delete_session(self, sid: str):
        self.r.delete(f"{self.PREFIX}{sid}")
    def count_tenant_sessions(self, tenant_id: str) -> int:
        count = 0
        for key in self.r.scan_iter(f"{self.PREFIX}*"):
            data = self.r.get(key)
            if data and json.loads(data).get("tenant_id") == tenant_id:
                count += 1
        return count

class EventBus:
    def __init__(self, r=None):
        self.r = r or get_redis()
    def publish(self, channel: str, message: dict):
        self.r.publish(channel, json.dumps(message))
    def subscribe(self, channel: str):
        ps = self.r.pubsub()
        ps.subscribe(channel)
        return ps
