"""
Configuration module for the Autonomous AI Task Worker.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).parent
load_dotenv(_project_root / ".env")


class Config:
    """Centralized configuration loaded from environment variables."""

    # LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Mock App
    MOCK_APP_HOST: str = os.getenv("MOCK_APP_HOST", "127.0.0.1")
    MOCK_APP_PORT: int = int(os.getenv("MOCK_APP_PORT", "8042"))
    MOCK_APP_URL: str = f"http://{MOCK_APP_HOST}:{MOCK_APP_PORT}"

    # Browser
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    BROWSER_TIMEOUT: int = int(os.getenv("BROWSER_TIMEOUT", "30000"))

    # Agent
    MAX_STEPS: int = int(os.getenv("MAX_STEPS", "20"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    HUMAN_APPROVAL_REQUIRED: bool = (
        os.getenv("HUMAN_APPROVAL_REQUIRED", "true").lower() == "true"
    )

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of configuration errors, empty if valid."""
        errors = []
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")
        return errors


config = Config()
