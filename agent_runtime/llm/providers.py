from abc import ABC, abstractmethod
import time, structlog
from shared.observability import LLM_LATENCY
logger = structlog.get_logger()

class BaseLLMProvider(ABC):
    @abstractmethod
    def create_initial_response(self, instruction: str, screenshot_b64: str) -> dict: ...
    @abstractmethod
    def create_continuation(self, prev_id: str, call_id: str, screenshot_b64: str) -> dict: ...

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def create_initial_response(self, instruction, screenshot_b64):
        t = time.time()
        r = self.client.responses.create(model=self.model, tools=[{"type": "computer"}], input=instruction)
        LLM_LATENCY.labels(provider="openai", model=self.model).observe(time.time() - t)
        return self._norm(r)

    def create_continuation(self, prev_id, call_id, screenshot_b64):
        t = time.time()
        r = self.client.responses.create(model=self.model, tools=[{"type": "computer"}],
            previous_response_id=prev_id, input=[{"type": "computer_call_output", "call_id": call_id,
                "output": {"type": "computer_screenshot",
                           "image_url": f"data:image/png;base64,{screenshot_b64}", "detail": "original"}}])
        LLM_LATENCY.labels(provider="openai", model=self.model).observe(time.time() - t)
        return self._norm(r)

    def _norm(self, response) -> dict:
        items = getattr(response, "output", [])
        cc, msgs = None, []
        for item in items:
            itype = item["type"] if isinstance(item, dict) else getattr(item, "type", None)
            if itype == "computer_call":
                acts = item["actions"] if isinstance(item, dict) else getattr(item, "actions", [])
                cid = item["call_id"] if isinstance(item, dict) else getattr(item, "call_id", "")
                cc = {"call_id": cid, "actions": [self._clean_action(a) for a in acts]}
            elif itype == "message":
                content = item["content"] if isinstance(item, dict) else getattr(item, "content", [])
                for c in content:
                    ct = c["type"] if isinstance(c, dict) else getattr(c, "type", None)
                    if ct in ("output_text", "text"):
                        msgs.append(c["text"] if isinstance(c, dict) else getattr(c, "text", ""))
        return {"id": getattr(response, "id", ""), "computer_call": cc, "messages": msgs,
                "usage": {"total_tokens": getattr(getattr(response, "usage", None), "total_tokens", 0)}}

    def _clean_action(self, action) -> dict:
        """Convert action object to clean dict, skipping Pydantic internals."""
        if isinstance(action, dict):
            return action
        if hasattr(action, "model_dump"):
            return action.model_dump(exclude_none=True)
        FIELDS = {"type", "x", "y", "button", "text", "keys", "scrollX", "scrollY", "url"}
        return {k: getattr(action, k) for k in FIELDS if hasattr(action, k)}

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def create_initial_response(self, instruction, screenshot_b64):
        t = time.time()
        r = self.client.messages.create(model=self.model, max_tokens=4096,
            tools=[{"type": "computer_20250124", "name": "computer",
                    "display_width_px": 1280, "display_height_px": 800, "display_number": 99}],
            messages=[{"role": "user", "content": [{"type": "text", "text": instruction},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64}}]}])
        LLM_LATENCY.labels(provider="anthropic", model=self.model).observe(time.time() - t)
        return self._norm(r)

    def create_continuation(self, prev_id, call_id, screenshot_b64):
        t = time.time()
        r = self.client.messages.create(model=self.model, max_tokens=4096,
            tools=[{"type": "computer_20250124", "name": "computer",
                    "display_width_px": 1280, "display_height_px": 800, "display_number": 99}],
            messages=[{"role": "user", "content": [{"type": "tool_result", "tool_use_id": call_id,
                "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64}}]}]}])
        LLM_LATENCY.labels(provider="anthropic", model=self.model).observe(time.time() - t)
        return self._norm(r)

    def _norm(self, r) -> dict:
        cc, msgs = None, []
        for b in r.content:
            if b.type == "tool_use" and b.name == "computer":
                cc = {"call_id": b.id, "actions": [b.input] if isinstance(b.input, dict) else []}
            elif b.type == "text": msgs.append(b.text)
        return {"id": r.id, "computer_call": cc, "messages": msgs,
                "usage": {"total_tokens": getattr(r.usage, "input_tokens", 0) + getattr(r.usage, "output_tokens", 0)}}
