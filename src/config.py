from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Redis Message Broker settings
    redis_url: str = "redis://localhost:6379/0"
    events_topic: str = "fomo.events"
    raw_events_topic: str = "fomo.raw_events"
    
    # Deduplication settings
    dedup_enabled: bool = True
    dedup_cache_ttl: int = 300
    dedup_prefix: str = "dedup:fingerprint:"
    dedup_use_local_fallback: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()
