import base64, json
from datetime import datetime
from shared.redis_client import EventBus

class StreamPublisher:
    def __init__(self, session_id: str):
        self.sid = session_id
        self.bus = EventBus()
        self.channel = f"session:{session_id}"

    def publish_screenshot(self, png_bytes, step):
        self._pub("screenshot", {"step": step, "size": len(png_bytes)})

    def publish_action(self, step, action, approved):
        self._pub("action", {"step": step, "action": action, "safety_approved": approved})

    def publish_status(self, status, message=""):
        self._pub("status", {"status": status, "message": message})

    def publish_error(self, error):
        self._pub("error", {"error": error})

    def publish_approval_request(self, step, action, reason):
        self._pub("approval_request", {"step": step, "action": action, "reason": reason})

    def _pub(self, etype, data):
        self.bus.publish(self.channel, {"type": etype, "session_id": self.sid,
            "data": data, "timestamp": datetime.utcnow().isoformat()})
