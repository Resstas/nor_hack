# src/models/entity.py

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
from src.core.base import BaseEntity, Named, Temporal, Identifiable
import uuid


class EntityType(Enum):
    MATERIAL = "material"
    PROCESS = "process"
    EXPERIMENT = "experiment"
    PUBLICATION = "publication"
    EQUIPMENT = "equipment"
    EXPERT = "expert"
    PARAMETER = "parameter"
    PROPERTY = "property"
    ORGANIZATION = "organization"


class RelationType(Enum):
    USES_MATERIAL = "USES_MATERIAL"
    USES_PROCESS = "USES_PROCESS"
    USES_EQUIPMENT = "USES_EQUIPMENT"
    PRODUCES = "PRODUCES"
    HAS_PARAMETER = "HAS_PARAMETER"
    HAS_PROPERTY = "HAS_PROPERTY"
    AUTHOR_OF = "AUTHOR_OF"
    DESCRIBES = "DESCRIBES"
    VALIDATES = "VALIDATES"
    CONTRADICTS = "CONTRADICTS"
    EXPERT_IN = "EXPERT_IN"
    WORKS_AT = "WORKS_AT"
    CITES = "CITES"
    RELATED_TO = "RELATED_TO"


@dataclass
class Entity(BaseEntity, Named, Temporal, Identifiable):
    """Базовая сущность графа знаний"""
    
    entity_type: EntityType = EntityType.MATERIAL
    tags: List[str] = field(default_factory=list)
    source: Optional[str] = None
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует сущность в словарь для Neo4j"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.entity_type.value,
            "tags": self.tags,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Entity':
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            entity_type=EntityType(data.get("type", "material")),
            tags=data.get("tags", []),
            source=data.get("source"),
            confidence=data.get("confidence", 1.0)
        )