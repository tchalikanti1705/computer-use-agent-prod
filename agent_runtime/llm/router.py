from agent_runtime.llm.providers import OpenAIProvider, AnthropicProvider, BaseLLMProvider
from shared.config import get_settings
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
logger = structlog.get_logger()

class LLMRouter:
    def __init__(self, tenant_config: dict):
        s = get_settings()
        self.pname = tenant_config.get("llm_provider", s.default_llm_provider)
        self.model = tenant_config.get("llm_model", s.default_llm_model)
        self.primary = self._build(self.pname, self.model)
        self.fallback = self._build_fallback()

    def _build(self, name, model) -> BaseLLMProvider:
        s = get_settings()
        if name == "openai": return OpenAIProvider(s.openai_api_key, model)
        if name == "anthropic": return AnthropicProvider(s.anthropic_api_key, model)
        raise ValueError(f"Unknown provider: {name}")

    def _build_fallback(self):
        s = get_settings()
        if self.pname == "openai" and s.anthropic_api_key: return AnthropicProvider(s.anthropic_api_key)
        if self.pname == "anthropic" and s.openai_api_key: return OpenAIProvider(s.openai_api_key)
        return None

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    def _call(self, method, **kw):
        try: return getattr(self.primary, method)(**kw)
        except Exception as e:
            logger.warning("llm_primary_failed", provider=self.pname, error=str(e))
            if self.fallback: return getattr(self.fallback, method)(**kw)
            raise

    def initial_response(self, instruction, screenshot_b64):
        return self._call("create_initial_response", instruction=instruction, screenshot_b64=screenshot_b64)

    def continuation(self, response_id, call_id, screenshot_b64):
        return self._call("create_continuation", prev_id=response_id, call_id=call_id, screenshot_b64=screenshot_b64)
