import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
import sys
import logging


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # App
    app_name: str = "Gameapy"
    app_version: str = "3.1.0"
    debug: bool = False
    environment: str = "development"
    
    # Database
    database_url: str = "sqlite:///gameapy.db"
    test_database_url: str = "sqlite:///gameapy_test.db"
    database_path: Optional[str] = None
    
    # OpenRouter
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    
    # LLM Models
    default_model: str = "anthropic/claude-3-haiku"
    fallback_model: str = "openai/gpt-3.5-turbo"
    
    # LLM Safety Parameters
    max_tokens: int = 1000
    temperature: float = 0.7
    timeout: int = 30
    
    # Retry Logic
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Entity Detection Settings
    recent_card_session_limit: int = 5  # Look back N sessions for recency loading (1-20)
    
    class Config:
        env_file = ".env"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate_recent_card_limit()
        
        # Set database path with Railway volume support
        if not self.database_path:
            # Check for Railway volume mount path (auto-injected)
            railway_volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
            if railway_volume:
                # Use Railway persistent volume
                self.database_path = os.path.join(railway_volume, "gameapy.db")
                os.makedirs(railway_volume, exist_ok=True)  # Ensure directory exists
            else:
                # Default to local development path
                self.database_path = "gameapy.db"
    
    def _validate_recent_card_limit(self):
        """Validate and enforce recent_card_session_limit."""
        min_val, max_val = 1, 20
        
        if not (min_val <= self.recent_card_session_limit <= max_val):
            error_msg = (
                f"RECENT_CARD_SESSION_LIMIT must be between {min_val} and {max_val}, "
                f"got {self.recent_card_session_limit}"
            )
            
            # Fail fast in dev/test
            if self.environment in ["development", "testing"]:
                raise ValueError(error_msg)
            
            # Log warning and fallback in production
            logger = logging.getLogger(__name__)
            logger.warning(f"{error_msg}. Falling back to default (5).")
            self.recent_card_session_limit = 5


# Global settings instance
settings = Settings()