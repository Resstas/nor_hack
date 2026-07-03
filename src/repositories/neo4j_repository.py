# src/repositories/neo4j_repository.py

from typing import Dict, Any, Optional, List
from neo4j import GraphDatabase, Session, Transaction
from dataclasses import dataclass, field

from src.core.interfaces import IGraphRepository
from src.core.exceptions import GraphStorageError
from src.models.entity import Entity
from src.utils.logger import Logger
from src.utils.config import Config


@dataclass
class Neo4jConfig:
    uri: str = Config.NEO4J_URI
    user: str = Config.NEO4J_USER
    password: str = Config.NEO4J_PASSWORD
    database: str = Config.NEO4J_DATABASE
    max_connection_pool_size: int = 10


class Neo4jRepository(IGraphRepository):
    
    def __init__(self, config: Optional[Neo4jConfig] = None):
        self.config = config or Neo4jConfig()
        self.logger = Logger(__name__)
        self._driver = None
        self._session = None
        self._transaction = None
        self._connect()
    
    def _connect(self):
        try:
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
                max_connection_pool_size=self.config.max_connection_pool_size
            )
            self.logger.info("Подключение к Neo4j установлено")
        except Exception as e:
            raise GraphStorageError(f"Ошибка подключения к Neo4j: {str(e)}")
    
    def _get_session(self) -> Session:
        if self._session is None:
            self._session = self._driver.session(database=self.config.database)
        return self._session
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        session = self._get_session()
        try:
            result = session.run(query, params or {})
            return [record.data() for record in result]
        except Exception as e:
            raise GraphStorageError(f"Ошибка выполнения запроса: {str(e)}")
    
    def begin_transaction(self) -> Transaction:
        if self._transaction is None:
            self._transaction = self._get_session().begin_transaction()
        return self._transaction
    
    def commit_transaction(self):
        if self._transaction:
            self._transaction.commit()
            self._transaction = None
    
    def rollback_transaction(self):
        if self._transaction:
            self._transaction.rollback()
            self._transaction = None
    
    def save_entity(self, entity: Entity) -> str:
        entity_data = entity.to_dict()
        entity_type = entity.entity_type.value if hasattr(entity, 'entity_type') else 'Entity'
        
        # Удаляем пустые значения
        clean_data = {}
        for key, value in entity_data.items():
            if value is not None and value != "" and value != {} and value != []:
                clean_data[key] = value
        
        query = f"""
        MERGE (e:{entity_type} {{id: $id}})
        SET e += $data
        RETURN e.id as entity_id
        """
        
        result = self.execute_query(query, {
            "id": entity.id,
            "data": clean_data
        })
        return result[0]['entity_id'] if result else entity.id
    
    def save_relation(self, source_id: str, target_id: str, relation_type: str, properties: Optional[Dict] = None):
        clean_props = {}
        if properties:
            for key, value in properties.items():
                if value is not None:
                    clean_props[key] = value
        
        query = f"""
        MATCH (a:Entity {{id: $source_id}})
        MATCH (b:Entity {{id: $target_id}})
        CREATE (a)-[r:{relation_type}]->(b)
        SET r += $properties
        RETURN r
        """
        self.execute_query(query, {
            "source_id": source_id,
            "target_id": target_id,
            "properties": clean_props
        })
    
    def query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        return self.execute_query(query, params)
    
    def find_by_property(self, entity_type: str, property_name: str, value: Any) -> List[Dict]:
        query = f"MATCH (e:{entity_type}) WHERE e[${property_name}] = ${value} RETURN e"
        return self.execute_query(query, {"property_name": property_name, "value": value})
    
    def find_by_parameters(self, param_name: str, param_value: Any, operator: str = "=") -> List[Dict]:
        query = f"MATCH (e:Entity)-[:HAS_PARAMETER]->(p:Parameter) WHERE p.name = $param_name AND p.value {operator} $param_value RETURN e, p"
        return self.execute_query(query, {"param_name": param_name, "param_value": param_value})
    
    def close(self):
        if self._session:
            self._session.close()
        if self._driver:
            self._driver.close()
        self.logger.info("Соединение с Neo4j закрыто")