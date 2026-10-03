from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "Price Tracker"
    database_url: str = "sqlite:///./price_tracker.db"
    price_check_interval_seconds: int = Field(default=60, ge=1)
    simulate_price_changes: bool = True
    scheduler_enabled: bool = True
