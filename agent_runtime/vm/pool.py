import docker, structlog
from shared.observability import VM_POOL_SIZE
logger = structlog.get_logger()
SANDBOX_IMAGE = "cua-sandbox:latest"

class VMPool:
    def __init__(self):
        self.client = docker.from_env()
        self._active: dict[str, str] = {}

    def create_sandbox(self, session_id: str, tenant_id: str) -> dict:
        name = f"cua-{tenant_id[:8]}-{session_id[:8]}"
        c = self.client.containers.run(SANDBOX_IMAGE, name=name, detach=True, remove=False,
            network_mode="none", mem_limit="1g", cpu_period=100000, cpu_quota=50000,
            security_opt=["no-new-privileges"], cap_drop=["ALL"], cap_add=["SYS_PTRACE"],
            ports={"5900/tcp": None})
        self._active[session_id] = c.id
        VM_POOL_SIZE.set(len(self._active))
        logger.info("sandbox_created", session_id=session_id, container=name)
        return {"container_id": c.id, "container_name": name}

    def destroy_sandbox(self, session_id: str):
        cid = self._active.pop(session_id, None)
        if not cid: return
        try:
            c = self.client.containers.get(cid)
            c.stop(timeout=5); c.remove(force=True)
        except docker.errors.NotFound: pass
        except Exception as e: logger.error("sandbox_destroy_failed", error=str(e))
        finally: VM_POOL_SIZE.set(len(self._active))

    def cleanup_all(self):
        for sid in list(self._active): self.destroy_sandbox(sid)
