from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Security settings
    auth_token: Optional[str] = None
    auth_header_name: str = "X-API-Key"
    max_payload_size_bytes: int = 65536  # Default limit: 64 KB
    
    # Redis Message Broker settings
    redis_url: str = "redis://localhost:6379/0"
    events_topic: str = "fomo.events"
    raw_events_topic: str = "fomo.raw_events"
    
    # Deduplication settings
    dedup_enabled: bool = True
    dedup_cache_ttl: int = 300
    dedup_prefix: str = "dedup:fingerprint:"
    dedup_use_local_fallback: bool = True
    
    # Health Monitoring and Self-Recovery
    health_check_interval_seconds: int = 15
    notification_rate_threshold_seconds: int = 60
    health_redis_check_key: str = "fomo.health.heartbeat"
    
    model_config = ConfigDict(env_file=".env")

settings = Settings()

