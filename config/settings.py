import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


    database_url: str = Field(
        default="postgresql://postgres:password@localhost:5432/ipl_dw",
        description="PostgreSQL connection string",
    )


    data_source_url: str = Field(
        default="https://cricsheet.org/downloads/ipl_json.zip",
        description="URL to download IPL JSON data",
    )


    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key for natural language analytics features",
    )
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model used for natural language SQL generation",
    )
    groq_api_url: str = Field(
        default="https://api.groq.com/openai/v1/chat/completions",
        description="Groq OpenAI-compatible chat completions endpoint",
    )


    raw_data_dir: Path = Field(
        default=Path("data/raw"),
        description="Directory for extracted raw JSON files",
    )
    processed_data_dir: Path = Field(
        default=Path("data/processed"),
        description="Directory for intermediate processed files",
    )
    rejected_data_dir: Path = Field(
        default=Path("data/rejected"),
        description="Directory for rejected/invalid files",
    )


    batch_size: int = Field(
        default=1000,
        description="Records per batch insert",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    etl_version: str = Field(
        default="1.0.0",
        description="Semantic version of the ETL pipeline",
    )
    enable_dq_checks: bool = Field(
        default=True,
        description="Toggle data quality checks after load",
    )
    api_cache_ttl_seconds: int = Field(
        default=300,
        description="TTL for cached analytics API responses in seconds",
    )
    analytics_query_row_limit: int = Field(
        default=200,
        description="Maximum rows returned by ad hoc analytics queries",
    )
    frontend_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated frontend origins allowed to call the FastAPI service",
    )
    serverless_runtime: bool = Field(
        default=False,
        description="Use serverless-safe runtime settings for platforms such as Netlify Functions",
    )


    streamlit_port: int = Field(
        default=8501,
        description="Port for Streamlit dashboard",
    )


    download_timeout_connect: int = Field(default=10)
    download_timeout_read: int = Field(default=60)
    download_max_retries: int = Field(default=3)

    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def ensure_directories(self) -> None:
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_data_dir.mkdir(parents=True, exist_ok=True)

    def get_frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    def is_serverless_runtime(self) -> bool:
        return (
            self.serverless_runtime
            or bool(os.getenv("NETLIFY"))
            or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
            or bool(os.getenv("VERCEL"))
            or bool(os.getenv("VERCEL_ENV"))
        )

def get_settings() -> Settings:
    return Settings()
