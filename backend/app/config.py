from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_path: str = "./proxy.db"
    jwt_secret: str = ""
    max_transaction_amount: str = "250.00"
    daily_spend_limit: str = "500.00"
    paypal_mode: str = "sandbox"
    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    cors_allowed_origins: str = "http://localhost:3000"\n    openai_api_key: str = ""\n    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()


def validate_runtime_config() -> None:
    if settings.app_env.lower() != "test" and len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be set to at least 32 characters outside tests")
    if settings.paypal_mode.lower() != "sandbox":
        raise RuntimeError("This MVP is sandbox-only; PAYPAL_MODE must be 'sandbox'")
