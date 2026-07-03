# src/services/graph_builder.py

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json
import re

from src.core.interfaces import IGraphRepository
from src.core.exceptions import GraphStorageError
from src.models.entity import Entity, EntityType, RelationType
from src.models.material import Material
from src.models.process import Process, ProcessType
from src.models.experiment import Experiment
from src.repositories.neo4j_repository import Neo4jRepository
from src.utils.logger import Logger


@dataclass
class GraphBuilderConfig:
    """Конфигурация построителя графа"""
    batch_size: int = 100
    create_indexes: bool = True
    use_transactions: bool = True


class GraphBuilder:
    """Сервис для построения графа знаний"""
    
    def __init__(
        self,
        repository: Optional[IGraphRepository] = None,
        config: Optional[GraphBuilderConfig] = None
    ):
        self.repository = repository or Neo4jRepository()
        self.config = config or GraphBuilderConfig()
        self.logger = Logger(__name__)
        
        if self.config.create_indexes:
            self._create_indexes()
    
    def _create_indexes(self):
        """Создает индексы в графе"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
            "CREATE INDEX IF NOT EXISTS FOR (m:Material) ON (m.name)",
            "CREATE INDEX IF NOT EXISTS FOR (p:Process) ON (p.name)",
        ]
        for query in indexes:
            try:
                self.repository.execute_query(query)
            except Exception as e:
                self.logger.warning(f"Ошибка создания индекса: {e}")
    
    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value)
    
    def _extract_value(self, data: Any) -> str:
        """Извлекает значение из вложенной структуры {'value': X, 'unit': 'Y'}"""
        if isinstance(data, dict):
            if 'value' in data:
                val = data.get('value', '')
                unit = data.get('unit', '')
                if unit:
                    return f"{val} {unit}".strip()
                return str(val)
            return str(data)
        return self._safe_str(data)
    
    def _extract_props(self, data: Dict) -> Dict[str, str]:
        """Извлекает плоские значения из словаря"""
        result = {}
        for key, value in data.items():
            if value is not None:
                result[key] = self._extract_value(value)
        return result
    
    def _get_process_type(self, type_str: str) -> ProcessType:
        """Определяет тип процесса"""
        if not type_str or type_str == "не указано":
            return ProcessType.UNKNOWN
        try:
            return ProcessType(type_str)
        except ValueError:
            return ProcessType.UNKNOWN
    
    def add_entity(self, entity: Entity) -> str:
        try:
            result = self.repository.save_entity(entity)
            return result
        except Exception as e:
            raise GraphStorageError(f"Ошибка добавления сущности: {str(e)}")
    
    def add_entities(self, entities: List[Entity]) -> List[str]:
        ids = []
        for entity in entities:
            try:
                entity_id = self.add_entity(entity)
                ids.append(entity_id)
            except Exception as e:
                self.logger.error(f"Ошибка добавления {entity.name}: {e}")
        return ids
    
    def add_relation(self, source_id: str, target_id: str, relation_type: RelationType, properties: Optional[Dict] = None):
        try:
            self.repository.save_relation(source_id, target_id, relation_type.value, properties or {})
        except Exception as e:
            self.logger.warning(f"Ошибка создания связи: {e}")
    
    def build_from_documents(self, documents: List[Dict[str, Any]]):
        total_saved = 0
        
        for doc_data in documents:
            if doc_data.get('status') != 'success':
                continue
            
            entities_data = doc_data.get('entities', {})
            entities = []
            doc_name = doc_data.get('doc_name', 'unknown')
            
            # Материалы
            for mat_data in entities_data.get('materials', []):
                try:
                    props = self._extract_props(mat_data.get('properties', {}))
                    material = Material(
                        name=self._safe_str(mat_data.get('name', '')),
                        formula=self._safe_str(mat_data.get('formula', '')),
                        material_type=self._safe_str(mat_data.get('type', 'руда')),
                        concentration=props.get('концентрация', ''),
                        unit=props.get('unit', ''),
                        confidence=0.8
                    )
                    entities.append(material)
                except Exception as e:
                    self.logger.warning(f"Ошибка создания материала: {e}")
            
            # Процессы
            for proc_data in entities_data.get('processes', []):
                try:
                    props = self._extract_props(proc_data.get('parameters', {}))
                    conds = self._extract_props(proc_data.get('conditions', {}))
                    
                    # Объединяем параметры
                    all_props = {**props, **conds}
                    
                    process = Process(
                        name=self._safe_str(proc_data.get('name', '')),
                        process_type=self._get_process_type(proc_data.get('type', '')),
                        temperature=all_props.get('температура', ''),
                        ph=all_props.get('pH', ''),
                        efficiency=all_props.get('эффективность', ''),
                        pressure=all_props.get('давление', ''),
                        flow_rate=all_props.get('скорость потока', ''),
                        current_density=all_props.get('плотность тока', ''),
                        confidence=0.8
                    )
                    entities.append(process)
                except Exception as e:
                    self.logger.warning(f"Ошибка создания процесса: {e}")
            
            # Эксперименты
            for exp_data in entities_data.get('experiments', []):
                try:
                    experiment = Experiment(
                        name=self._safe_str(exp_data.get('name', '')),
                        conditions=self._safe_str(exp_data.get('conditions', '')),
                        results=self._safe_str(exp_data.get('results', '')),
                        confidence=0.8
                    )
                    entities.append(experiment)
                except Exception as e:
                    self.logger.warning(f"Ошибка создания эксперимента: {e}")
            
            if entities:
                self.logger.info(f"Добавление {len(entities)} сущностей из {doc_name}")
                entity_ids = self.add_entities(entities)
                total_saved += len(entity_ids)
                self.logger.info(f"Добавлено {len(entity_ids)} сущностей (всего: {total_saved})")
            
            if len(entities) > 1:
                for i in range(len(entities) - 1):
                    self.add_relation(
                        entities[i].id,
                        entities[i + 1].id,
                        RelationType.RELATED_TO,
                        {"context": f"извлечено из {doc_name}"}
                    )
            
            self.logger.info(f"Обработан документ: {doc_name}")
    
    def get_statistics(self) -> Dict[str, int]:
        stats = {}
        for entity_type in ["Entity", "Material", "Process", "Experiment"]:
            try:
                query = f"MATCH (e:{entity_type}) RETURN count(e) as count"
                result = self.repository.execute_query(query)
                stats[entity_type.lower()] = result[0]['count'] if result else 0
            except Exception as e:
                self.logger.warning(f"Ошибка статистики {entity_type}: {e}")
                stats[entity_type.lower()] = 0
        return stats