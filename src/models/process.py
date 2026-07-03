# src/models/process.py

from dataclasses import dataclass, field
from typing import Dict, Any
from enum import Enum
from src.models.entity import Entity, EntityType


class ProcessType(Enum):
    HYDROMETALLURGY = "гидрометаллургия"
    PYROMETALLURGY = "пирометаллургия"
    ECOLOGY = "экология"
    WASTE_PROCESSING = "переработка_отходов"
    UNKNOWN = "не указано"


@dataclass
class Process(Entity):
    """Модель технологического процесса"""
    
    process_type: ProcessType = ProcessType.UNKNOWN
    temperature: str = ""
    ph: str = ""
    efficiency: str = ""
    pressure: str = ""
    flow_rate: str = ""
    current_density: str = ""
    
    def __post_init__(self):
        self.entity_type = EntityType.PROCESS
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["process_type"] = self.process_type.value
        if self.temperature:
            data["temperature"] = self.temperature
        if self.ph:
            data["ph"] = self.ph
        if self.efficiency:
            data["efficiency"] = self.efficiency
        if self.pressure:
            data["pressure"] = self.pressure
        if self.flow_rate:
            data["flow_rate"] = self.flow_rate
        if self.current_density:
            data["current_density"] = self.current_density
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Process':
        proc_type = data.get("process_type", "не указано")
        try:
            proc_type_enum = ProcessType(proc_type)
        except ValueError:
            proc_type_enum = ProcessType.UNKNOWN
        
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            process_type=proc_type_enum,
            temperature=data.get("temperature", ""),
            ph=data.get("ph", ""),
            efficiency=data.get("efficiency", ""),
            pressure=data.get("pressure", ""),
            flow_rate=data.get("flow_rate", ""),
            current_density=data.get("current_density", ""),
            tags=data.get("tags", []),
            source=data.get("source"),
            confidence=data.get("confidence", 1.0)
        )