# src/models/material.py

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from src.models.entity import Entity, EntityType


@dataclass
class Material(Entity):
    """Модель материала"""
    
    formula: str = ""
    material_type: str = "руда"
    concentration: str = ""
    unit: str = ""
    
    def __post_init__(self):
        self.entity_type = EntityType.MATERIAL
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        if self.formula:
            data["formula"] = self.formula
        if self.material_type:
            data["material_type"] = self.material_type
        if self.concentration:
            data["concentration"] = self.concentration
        if self.unit:
            data["unit"] = self.unit
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Material':
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            formula=data.get("formula", ""),
            material_type=data.get("material_type", "руда"),
            concentration=data.get("concentration", ""),
            unit=data.get("unit", ""),
            tags=data.get("tags", []),
            source=data.get("source"),
            confidence=data.get("confidence", 1.0)
        )