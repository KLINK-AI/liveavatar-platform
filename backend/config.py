"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "LiveAvatar Platform"
    app_env: str = "development"
    app_secret_key: str = "change-me"
    app_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://liveavatar:liveavatar@localhost:5432/liveavatar"

    # LiveAvatar LITE Mode API
    liveavatar_api_key: str = ""
    liveavatar_api_base: str = "https://api.liveavatar.com"

    # TTS — ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_default_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_turbo_model_id: str = "eleven_turbo_v2_5"  # Faster model for greetings
    tts_sample_rate: int = 24000  # PCM 16Bit 24KHz for LiveAvatar LITE

    # STT — Deepgram + OpenAI Whisper
    stt_provider: str = "deepgram"  # "deepgram" or "openai"
    deepgram_api_key: str = ""
    deepgram_model: str = "nova-2"
    deepgram_language: str = "de"  # German default

    # LiveKit
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4o"

    # Vector DB
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # Embeddings
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

    # Admin credentials
    admin_username: str = "admin"
    admin_password: str = "change-me"

    # JWT
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.app_cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
