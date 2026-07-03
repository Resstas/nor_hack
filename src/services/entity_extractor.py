from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from src.core.interfaces import IEntityExtractor
from src.core.exceptions import EntityExtractionError
from src.models.document import Document
from src.models.entity import Entity
from src.models.material import Material
from src.models.process import Process, ProcessType
from src.services.ai_service import YandexAIService
from src.utils.logger import Logger


@dataclass
class ExtractorConfig:
    """Конфигурация экстрактора"""
    min_confidence: float = 0.7
    max_entities_per_doc: int = 50
    extract_materials: bool = True
    extract_processes: bool = True
    extract_experiments: bool = True
    extract_equipment: bool = True


class EntityExtractor(IEntityExtractor):
    """Экстрактор сущностей из текста"""
    
    def __init__(
        self,
        ai_service: Optional[YandexAIService] = None,
        config: Optional[ExtractorConfig] = None
    ):
        self.ai_service = ai_service or YandexAIService()
        self.config = config or ExtractorConfig()
        self.logger = Logger(__name__)
    
    def extract(self, text: str) -> Dict[str, Any]:
        """Извлекает сущности из текста"""
        
        if not text or len(text.strip()) < 10:
            return {"error": "Текст слишком короткий"}
        
        try:
            raw_entities = self.ai_service.extract_entities(text)
            
            if "error" in raw_entities:
                raise EntityExtractionError(raw_entities["error"])
            
            entities = self._convert_to_entities(raw_entities)
            
            return {
                "status": "success",
                "entities": entities,
                "raw": raw_entities
            }
            
        except Exception as e:
            raise EntityExtractionError(f"Ошибка извлечения: {str(e)}")
    
    def extract_batch(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """Извлекает сущности из нескольких документов"""
        
        results = []
        for i, doc in enumerate(documents):
            self.logger.info(f"Обработка {i+1}/{len(documents)}: {doc.name}")
            
            try:
                result = self.extract(doc.text)
                results.append({
                    "doc_id": doc.id,
                    "doc_name": doc.name,
                    "status": "success",
                    "entities": result
                })
            except Exception as e:
                self.logger.error(f"Ошибка: {str(e)}")
                results.append({
                    "doc_id": doc.id,
                    "doc_name": doc.name,
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    def _convert_to_entities(self, raw_data: Dict[str, Any]) -> List[Entity]:
        """Преобразует сырые данные в объекты Entity"""
        
        entities = []
        
        if self.config.extract_materials and 'materials' in raw_data:
            for mat_data in raw_data['materials']:
                try:
                    material = Material(
                        name=mat_data.get('name', ''),
                        formula=mat_data.get('formula', ''),
                        material_type=mat_data.get('type', 'руда'),
                        properties=mat_data.get('properties', {}),
                        confidence=min(1.0, self.config.min_confidence + 0.1)
                    )
                    entities.append(material)
                except Exception as e:
                    self.logger.warning(f"Ошибка конвертации материала: {e}")
        
        if self.config.extract_processes and 'processes' in raw_data:
            for proc_data in raw_data['processes']:
                try:
                    process = Process(
                        name=proc_data.get('name', ''),
                        process_type=ProcessType(proc_data.get('type', 'гидрометаллургия')),
                        conditions=proc_data.get('conditions', {}),
                        parameters=proc_data.get('parameters', {}),
                        confidence=min(1.0, self.config.min_confidence + 0.1)
                    )
                    entities.append(process)
                except Exception as e:
                    self.logger.warning(f"Ошибка конвертации процесса: {e}")
        
        return entities