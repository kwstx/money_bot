from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Redis Message Broker settings
    redis_url: str = "redis://localhost:6379/0"
    events_topic: str = "fomo.events"
    
    class Config:
        env_file = ".env"

settings = Settings()
