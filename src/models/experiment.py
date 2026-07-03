# src/models/experiment.py

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from src.models.entity import Entity, EntityType


@dataclass
class Experiment(Entity):
    """Модель эксперимента"""
    
    date: str = ""
    protocol: str = ""
    laboratory: str = ""
    lead_researcher: str = ""
    conditions: str = ""
    results: str = ""
    materials_used: List[str] = field(default_factory=list)
    equipment_used: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.entity_type = EntityType.EXPERIMENT
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        if self.date:
            data["date"] = self.date
        if self.protocol:
            data["protocol"] = self.protocol
        if self.laboratory:
            data["laboratory"] = self.laboratory
        if self.lead_researcher:
            data["lead_researcher"] = self.lead_researcher
        if self.conditions:
            data["conditions"] = self.conditions
        if self.results:
            data["results"] = self.results
        if self.materials_used:
            data["materials_used"] = self.materials_used
        if self.equipment_used:
            data["equipment_used"] = self.equipment_used
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Experiment':
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            date=data.get("date", ""),
            protocol=data.get("protocol", ""),
            laboratory=data.get("laboratory", ""),
            lead_researcher=data.get("lead_researcher", ""),
            conditions=data.get("conditions", ""),
            results=data.get("results", ""),
            materials_used=data.get("materials_used", []),
            equipment_used=data.get("equipment_used", []),
            tags=data.get("tags", []),
            source=data.get("source"),
            confidence=data.get("confidence", 1.0)
        )