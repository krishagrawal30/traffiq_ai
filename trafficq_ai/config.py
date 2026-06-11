"""
TRAFFICQ AI — Configuration
All settings loaded from environment / .env file.
"""
from __future__ import annotations
import os
from functools import lru_cache

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict  # pydantic v2

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

        model_config = SettingsConfigDict(
            env_file=os.path.join(os.path.dirname(__file__), ".env"),
            env_file_encoding="utf-8",
            extra="ignore"
        )

except ImportError:
    # Fallback when pydantic-settings is not installed
    class Settings:  # type: ignore[no-redef]
        """Lightweight fallback settings loaded from environment variables."""
        def __init__(self) -> None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
            self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
            self.azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            self.azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            self.azure_openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
            self.azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
            self.llm_provider = os.getenv("LLM_PROVIDER", "openai")
            self.app_host = os.getenv("APP_HOST", "0.0.0.0")
            self.app_port = int(os.getenv("APP_PORT", "8000"))
            self.app_env = os.getenv("APP_ENV", "development")
            self.log_level = os.getenv("LOG_LEVEL", "INFO")
            self.sim_fps = int(os.getenv("SIM_FPS", "20"))
            self.sim_max_vehicles = int(os.getenv("SIM_MAX_VEHICLES", "100"))
            self.sim_cycle_seconds = int(os.getenv("SIM_CYCLE_SECONDS", "60"))
            self.sim_min_green_seconds = int(os.getenv("SIM_MIN_GREEN_SECONDS", "15"))
            self.sim_seed = int(os.getenv("SIM_SEED", "42"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

