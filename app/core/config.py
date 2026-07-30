import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Chatbot AI Service"
    app_version: str = "1.0.0"
    database_url: str = "postgresql://postgres:postgres@postgres:5432/chatbot_db"
    
    azure_openai_model_1: str = "gpt-5.4-mini"
    azure_openai_endpoint_1: str = ""
    azure_openai_api_key_1: str = ""
    
    # AWS S3 Settings
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = ""
    s3_bucket: str = ""
    s3_public_base_url: str = ""

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
