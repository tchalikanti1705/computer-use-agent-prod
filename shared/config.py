from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4o"
    database_url: str = "postgresql://agent:agent_secret@localhost:5432/agent_platform"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "agent-artifacts"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    max_agent_steps: int = 50
    step_delay_seconds: float = 1.0
    screenshot_quality: int = 85
    vm_idle_timeout_seconds: int = 300
    vm_max_lifetime_seconds: int = 1800
    log_level: str = "INFO"
    enable_tracing: bool = False
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
