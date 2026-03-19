import time
from fastapi import HTTPException
from shared.redis_client import get_redis

class RateLimiter:
    def __init__(self, rpm: int = 60):
        self.rpm = rpm
        self.redis = get_redis()
    async def check(self, tenant_id: str):
        key = f"ratelimit:{tenant_id}"
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - 60)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, 120)
        _, _, count, _ = pipe.execute()
        if count > self.rpm:
            raise HTTPException(429, "Rate limit exceeded")

rate_limiter = RateLimiter()
