from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid


@dataclass
class BaseEntity(ABC):
    """Базовый класс для всех сущностей"""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует сущность в словарь"""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEntity':
        """Создает сущность из словаря"""
        pass
    
    def validate(self) -> bool:
        """Валидирует сущность"""
        return True


@dataclass
class Identifiable:
    """Миксин для сущностей с идентификатором"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Temporal:
    """Миксин для сущностей с временными метками"""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Named:
    """Миксин для именованных сущностей"""
    name: str = ""
    description: str = ""