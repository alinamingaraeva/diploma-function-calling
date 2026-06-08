"""Настройки приложения. Загружает ключи из .env файла"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Настройки приложения"""
    polza_ai_api_key: str  # API ключ от Polza
    
    class Config:
        env_file = ".env"
        # Указываем, что имя переменной в .env файле - POLZA_AI_API_KEY,
        # и мы хотим сохранить ее в атрибут polza_ai_api_key
        env_prefix = ""
        extra = "ignore"

# Создаём один объект с настройками для всего приложения
settings = Settings()