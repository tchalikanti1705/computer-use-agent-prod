from urllib.parse import urlparse
from agent_runtime.safety.policies import GLOBAL_BLOCKED_DOMAINS, RISKY_KEYWORDS, SAFE_ACTIONS, MAX_ACTIONS_PER_STEP
from shared.observability import SAFETY_BLOCKS
import structlog
logger = structlog.get_logger()

class SafetyVerdict:
    def __init__(self, allowed: bool, reason: str = ""):
        self.allowed = allowed
        self.reason = reason

class SafetyEngine:
    def __init__(self, tenant_id: str, tenant_config: dict):
        self.tenant_id = tenant_id
        self.allowed_domains = set(tenant_config.get("allowed_domains", []))
        self.require_approval = tenant_config.get("require_human_approval", False)
        self.blocked_domains = GLOBAL_BLOCKED_DOMAINS | set(tenant_config.get("blocked_domains", []))

    def validate_action(self, action: dict) -> SafetyVerdict:
        atype = action.get("type", "")
        if atype in SAFE_ACTIONS:
            return SafetyVerdict(True)
        if atype == "type":
            text = action.get("text", "")
            if text.startswith("http://") or text.startswith("https://"):
                return self._check_url(text)
            if self._text_is_risky(text):
                return SafetyVerdict(not self.require_approval, f"Risky text: {text[:50]}")
        if atype == "keypress":
            return self._check_keys(action.get("keys", []))
        return SafetyVerdict(True)

    def validate_batch(self, actions: list[dict]) -> SafetyVerdict:
        if len(actions) > MAX_ACTIONS_PER_STEP:
            return SafetyVerdict(False, f"Too many actions: {len(actions)}")
        for a in actions:
            v = self.validate_action(a)
            if not v.allowed:
                SAFETY_BLOCKS.labels(tenant_id=self.tenant_id, reason=v.reason[:50]).inc()
                return v
        return SafetyVerdict(True)

    def _check_url(self, url: str) -> SafetyVerdict:
        try: domain = urlparse(url).netloc.lower()
        except: return SafetyVerdict(False, f"Invalid URL: {url}")
        if domain in self.blocked_domains:
            return SafetyVerdict(False, f"Blocked domain: {domain}")
        if self.allowed_domains:
            base = ".".join(domain.split(".")[-2:])
            if domain not in self.allowed_domains and base not in self.allowed_domains and f"www.{base}" not in self.allowed_domains:
                return SafetyVerdict(False, f"Domain not allowed: {domain}")
        return SafetyVerdict(True)

    def _check_keys(self, keys: list) -> SafetyVerdict:
        ks = " ".join(str(k).lower() for k in keys)
        if "alt" in ks and "f4" in ks: return SafetyVerdict(False, "Alt+F4 blocked")
        if "ctrl" in ks and "alt" in ks and "delete" in ks: return SafetyVerdict(False, "Ctrl+Alt+Del blocked")
        return SafetyVerdict(True)

    def _text_is_risky(self, text: str) -> bool:
        t = text.lower()
        return any(w in t for w in RISKY_KEYWORDS)
