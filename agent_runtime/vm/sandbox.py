from agent_runtime.vm.pool import VMPool
from agent_runtime.vm.controller import VMController
import time, structlog
logger = structlog.get_logger()

class SandboxSession:
    def __init__(self, pool: VMPool):
        self.pool = pool
        self.controller = None
        self.container_info = {}
        self.session_id = ""

    def start(self, session_id: str, tenant_id: str) -> VMController:
        self.session_id = session_id
        self.container_info = self.pool.create_sandbox(session_id, tenant_id)
        self.controller = VMController(self.container_info["container_name"])
        for _ in range(10):
            if self.controller.is_alive(): break
            time.sleep(1)
        else: raise RuntimeError("Sandbox failed to start")
        self.controller.ensure_firefox(wait=3)
        return self.controller

    def stop(self):
        self.pool.destroy_sandbox(self.session_id)
        self.controller = None
