"""
TRAFFICQ AI — Configuration
All settings loaded from environment / .env file.
"""
from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings  # pydantic v2


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-02-01"

    llm_provider: str = "openai"          # "openai" | "azure"

    # ── App ──────────────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"
    log_level: str = "INFO"

    # ── Simulation ────────────────────────────────────────────────────────────
    sim_fps: int = 20
    sim_max_vehicles: int = 100
    sim_cycle_seconds: int = 60
    sim_min_green_seconds: int = 15
    sim_seed: int = 42

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
