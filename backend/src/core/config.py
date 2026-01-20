from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Azure Form Recognizer
    AZURE_FORM_RECOGNIZER_ENDPOINT: str
    AZURE_FORM_RECOGNIZER_KEY: str

    # MinIO/S3 (optional - can be empty for local development without MinIO)
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "invoiceflow"
    MINIO_USE_SSL: bool = False

    # CORS - can be "*" for all origins, or comma-separated list
    # In Docker, frontend requests come from the Docker network, so allow all in development
    # Allow all origins in development (change in production)
    CORS_ORIGINS: str = "*"

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # File upload
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_PAGES: int = 100
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".docx"]

    # LLM (optional, for enhanced extraction)
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"  # Fast and cost-effective
    USE_LLM_FOR_EXTRACTION: bool = True  # Enable LLM enhancement

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
