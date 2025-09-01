# app/config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env 
load_dotenv()

@dataclass
class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "dev")
    DB_URL: str = os.getenv("DB_URL", "sqlite:///./app.db")
    CLICKUP_TOKEN: str = os.getenv("CLICKUP_TOKEN", "")
    CLICKUP_LIST_ID: str = os.getenv("CLICKUP_LIST_ID", "")
    CLICKUP_DEFAULT_STATUS: str = os.getenv("CLICKUP_DEFAULT_STATUS", "Open")
    FORM_SHARED_SECRET: str = os.getenv("FORM_SHARED_SECRET", "")
    SUBTASKS: str = os.getenv(
        "SUBTASKS",
        "Contact lead (24h);Send info;Propose 3 slots;Schedule intro meeting",
    )

# Instantiate the Settings class
settings = Settings()

def get_settings() -> Settings:
    return settings
