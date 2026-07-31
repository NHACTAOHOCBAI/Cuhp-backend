import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Cuhp Service"
    app_version: str = "1.0.0"
    database_url: str = "postgresql://postgres:postgres@postgres:5432/cuhp_db"
    
    azure_openai_model_1: str = "gpt-5.4-mini"
    azure_openai_endpoint_1: str = ""
    azure_openai_api_key_1: str = ""
    

    # Cloudflare R2 Settings
    r2_endpoint: str = ""
    r2_access_key: str = ""
    r2_secret_key: str = ""
    r2_bucket: str = "mora-documents"
    r2_public_url: str = ""

    # Facebook Messenger Settings (Reload Triggered)
    fb_page_access_token: str = ""
    fb_verify_token: str = ""
    
    # Environment config loading
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
