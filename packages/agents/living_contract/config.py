"""Centralized configuration — loads from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Blockchain
    rpc_url: str               = Field(..., env="RPC_URL")
    chain_id: int              = Field(11155111, env="CHAIN_ID")  # Sepolia default
    agent_private_key: str     = Field(..., env="AGENT_PRIVATE_KEY")
    contract_address: str      = Field(..., env="CONTRACT_ADDRESS")
    audit_log_address: str     = Field(..., env="AUDIT_LOG_ADDRESS")

    # AI — supports OpenAI and Groq (Groq uses same OpenAI SDK with different base_url)
    openai_api_key: str        = Field(..., env="OPENAI_API_KEY")
    llm_model: str             = Field("llama-3.3-70b-versatile", env="LLM_MODEL")

    # Redis
    redis_url: str             = Field("redis://redis:6379/0", env="REDIS_URL")

    # Pipeline
    poll_interval_seconds: int = Field(300, env="POLL_INTERVAL_SECONDS")
    min_data_quality_score: float = Field(0.90, env="MIN_DATA_QUALITY_SCORE")

    # Logging
    log_level: str             = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
