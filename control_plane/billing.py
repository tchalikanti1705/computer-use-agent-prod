from datetime import datetime
from shared.redis_client import get_redis
import json

class UsageMeter:
    PREFIX = "billing:usage:"
    def __init__(self):
        self.redis = get_redis()
    def record(self, tenant_id, tokens=0, vm_seconds=0, actions=0, screenshots=0):
        self.redis.rpush(f"{self.PREFIX}{tenant_id}", json.dumps({
            "tokens": tokens, "vm_seconds": vm_seconds, "actions": actions,
            "screenshots": screenshots, "timestamp": datetime.utcnow().isoformat()}))
    def get_usage(self, tenant_id) -> dict:
        totals = {"tokens": 0, "vm_seconds": 0, "actions": 0, "screenshots": 0}
        for raw in self.redis.lrange(f"{self.PREFIX}{tenant_id}", 0, -1):
            for k in totals: totals[k] += json.loads(raw).get(k, 0)
        return totals
