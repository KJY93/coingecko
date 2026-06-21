from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env"
    )
    mongodb_url:str
    mongodb_db_name:str
    redis_url:str
    coingecko_base_url:str
    scheduler_interval_seconds:int
    cache_ttl_seconds:int
    coingecko_apikey:str
    coins_refresh_hours: int
    jwt_secret_key:str
    jwt_algorithm:str
    jwt_expire_minutes:int
    rabbitmq_url:str

settings = Settings()