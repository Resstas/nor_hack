# src/utils/config.py

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Глобальная конфигурация приложения"""
    
    # Neo4j
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")
    
    # Yandex AI
    YANDEX_API_KEY: str = os.getenv("YANDEX_API_KEY", "")
    YANDEX_FOLDER_ID: str = os.getenv("YANDEX_FOLDER_ID", "")
    YANDEX_MODEL: str = os.getenv("YANDEX_MODEL", "aliceai-llm")
    
    # Data
    DATA_DIR: str = os.getenv("DATA_DIR", "data/")
    RAW_DATA_DIR: str = os.getenv("RAW_DATA_DIR", "data/raw/")
    PROCESSED_DATA_DIR: str = os.getenv("PROCESSED_DATA_DIR", "data/processed/")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "app.log")
    
    @classmethod
    def validate(cls) -> bool:
        """Проверяет наличие необходимых конфигураций"""
        errors = []
        
        if not cls.YANDEX_API_KEY:
            errors.append("YANDEX_API_KEY не установлен")
        if not cls.YANDEX_FOLDER_ID:
            errors.append("YANDEX_FOLDER_ID не установлен")
        
        if errors:
            raise ValueError(f"Ошибки конфигурации: {', '.join(errors)}")
        
        return True