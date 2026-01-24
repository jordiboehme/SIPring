"""Application configuration."""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Data storage
    data_dir: str = "/data"

    # Web server
    host: str = "0.0.0.0"
    port: int = 8080

    # Optional basic auth
    username: Optional[str] = None
    password: Optional[str] = None

    # SIP defaults
    default_sip_port: int = 5060
    default_local_port: int = 5062
    default_ring_duration: int = 30

    # Logging
    log_level: str = "INFO"

    model_config = {
        "env_prefix": "SIPRING_",
        "env_file": ".env",
    }

    @property
    def config_file(self) -> str:
        """Path to config.json file."""
        return os.path.join(self.data_dir, "config.json")

    @property
    def auth_enabled(self) -> bool:
        """Check if basic auth is enabled."""
        return bool(self.username and self.password)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
