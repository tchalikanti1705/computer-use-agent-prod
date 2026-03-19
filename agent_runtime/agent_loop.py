import time, base64, structlog
from agent_runtime.safety import SafetyEngine
from agent_runtime.vm.controller import VMController
from agent_runtime.llm.router import LLMRouter
from agent_runtime.streaming.publisher import StreamPublisher
from shared.config import get_settings
from shared.storage import ArtifactStore
from shared.observability import AGENT_STEPS, TASKS_COMPLETED
logger = structlog.get_logger()

KEY_MAP = {"ENTER":"Return","RETURN":"Return","SPACE":"space","TAB":"Tab","ESC":"Escape",
    "ESCAPE":"Escape","BACKSPACE":"BackSpace","DELETE":"Delete","UP":"Up","DOWN":"Down",
    "LEFT":"Left","RIGHT":"Right","HOME":"Home","END":"End","PAGEUP":"Page_Up",
    "PAGEDOWN":"Page_Down","CTRL":"ctrl","CONTROL":"ctrl","ALT":"alt","SHIFT":"shift","CMD":"super","SUPER":"super"}

def map_key(k): return KEY_MAP.get(str(k).upper(), str(k))

class AgentLoop:
    """Production agent loop: Reason -> Safety -> Act -> Observe -> Repeat"""

    def __init__(self, task_id, tenant_id, tenant_config, vm: VMController, session_id):
        self.task_id = task_id
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.vm = vm
        self.settings = get_settings()
        self.safety = SafetyEngine(tenant_id, tenant_config)
        self.llm = LLMRouter(tenant_config)
        self.publisher = StreamPublisher(session_id)
        self.artifacts = ArtifactStore()
        self.step = 0
        self.total_tokens = 0
        self.response_id = None

    def run(self, instruction: str) -> dict:
        logger.info("agent_loop_start", task_id=self.task_id, instruction=instruction[:100])
        self.publisher.publish_status("running", "Agent started")
        try:
            # Initial screenshot + first LLM call
            ss = self.vm.capture_screenshot_base64()
            self._store_screenshot(ss)
            resp = self.llm.initial_response(instruction, ss)
            self.response_id = resp["id"]
            self.total_tokens += resp["usage"]["total_tokens"]
            for m in resp.get("messages", []): logger.info("model_msg", step=self.step, msg=m[:200])

            while self.step < self.settings.max_agent_steps:
                cc = resp.get("computer_call")
                if not cc:
                    self.publisher.publish_status("completed")
                    return self._result("completed", resp.get("messages", []))

                actions = cc.get("actions", [])
                call_id = cc.get("call_id", "")

                # Safety gate
                verdict = self.safety.validate_batch(actions)
                if not verdict.allowed:
                    logger.warning("safety_blocked", step=self.step, reason=verdict.reason)
                    self.publisher.publish_error(f"Safety: {verdict.reason}")
                    return self._result("failed", error=verdict.reason)

                # Execute
                self._execute(actions)
                self.step += 1
                AGENT_STEPS.labels(tenant_id=self.tenant_id).inc()

                # New screenshot
                time.sleep(self.settings.step_delay_seconds)
                ss = self.vm.capture_screenshot_base64()
                self._store_screenshot(ss)
                self.publisher.publish_screenshot(self.vm.capture_screenshot(), self.step)

                # Continue LLM
                resp = self.llm.continuation(self.response_id, call_id, ss)
                self.response_id = resp["id"]
                self.total_tokens += resp["usage"]["total_tokens"]
                for m in resp.get("messages", []): logger.info("model_msg", step=self.step, msg=m[:200])

            self.publisher.publish_status("failed", "Max steps exceeded")
            return self._result("failed", error="Max steps exceeded")
        except Exception as e:
            logger.exception("agent_loop_error", task_id=self.task_id)
            self.publisher.publish_error(str(e))
            return self._result("failed", error=str(e))

    def _execute(self, actions):
        for a in actions:
            atype = a.get("type", "")
            self.publisher.publish_action(self.step, a, True)
            if atype == "click":
                self.vm.click(a["x"], a["y"], {"left":1,"middle":2,"right":3}.get(a.get("button","left"),1))
            elif atype == "double_click":
                self.vm.double_click(a["x"], a["y"], {"left":1,"middle":2,"right":3}.get(a.get("button","left"),1))
            elif atype == "move":
                self.vm.mouse_move(a["x"], a["y"])
            elif atype == "scroll":
                self.vm.mouse_move(a.get("x",0), a.get("y",0))
                sy = a.get("scrollY", 0)
                if sy > 0: self.vm.scroll("down", max(1, abs(sy)//200))
                elif sy < 0: self.vm.scroll("up", max(1, abs(sy)//200))
            elif atype == "keypress":
                mapped = [map_key(k) for k in a.get("keys", [])]
                self.vm.keypress("+".join(mapped) if len(mapped) > 1 else mapped[0])
            elif atype == "type":
                self.vm.type_text(a.get("text", ""))
            elif atype == "wait":
                time.sleep(2)

    def _store_screenshot(self, b64):
        key = f"{self.tenant_id}/{self.session_id}/step_{self.step:04d}.png"
        try: self.artifacts.upload_screenshot(key, base64.b64decode(b64))
        except Exception as e: logger.warning("ss_store_fail", error=str(e))

    def _result(self, status, messages=None, error=None):
        TASKS_COMPLETED.labels(tenant_id=self.tenant_id, status=status).inc()
        return {"status": status, "steps": self.step, "total_tokens": self.total_tokens,
                "messages": messages or [], "error": error}
