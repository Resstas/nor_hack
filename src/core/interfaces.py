from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class IDocumentLoader(ABC):
    """Интерфейс загрузчика документов"""
    
    @abstractmethod
    def load(self, source: str) -> List['Document']:
        """Загружает документы из источника"""
        pass
    
    @abstractmethod
    def load_single(self, file_path: str) -> 'Document':
        """Загружает один документ"""
        pass


class IEntityExtractor(ABC):
    """Интерфейс экстрактора сущностей"""
    
    @abstractmethod
    def extract(self, text: str) -> Dict[str, Any]:
        """Извлекает сущности из текста"""
        pass
    
    @abstractmethod
    def extract_batch(self, documents: List['Document']) -> List[Dict[str, Any]]:
        """Извлекает сущности из нескольких документов"""
        pass


class IGraphRepository(ABC):
    """Интерфейс репозитория графа"""
    
    @abstractmethod
    def save_entity(self, entity: 'Entity') -> str:
        """Сохраняет сущность в граф"""
        pass
    
    @abstractmethod
    def save_relation(self, source: str, target: str, relation_type: str, properties: Dict = None):
        """Сохраняет связь между сущностями"""
        pass
    
    @abstractmethod
    def query(self, query: str, params: Dict = None) -> List[Dict]:
        """Выполняет запрос к графу"""
        pass
    
    @abstractmethod
    def find_by_property(self, entity_type: str, property_name: str, value: Any) -> List[Dict]:
        """Ищет сущности по свойству"""
        pass


class IAService(ABC):
    """Интерфейс AI сервиса"""
    
    @abstractmethod
    def generate_response(self, prompt: str, context: Optional[str] = None) -> str:
        """Генерирует ответ на запрос"""
        pass
    
    @abstractmethod
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Извлекает сущности с помощью AI"""
        pass
    
    @abstractmethod
    def summarize(self, texts: List[str]) -> str:
        """Создает суммаризацию текстов"""
        pass


class ISearchEngine(ABC):
    """Интерфейс поисковой системы"""
    
    @abstractmethod
    def search(self, query: str, filters: Dict = None) -> List[Dict]:
        """Выполняет поиск"""
        pass
    
    @abstractmethod
    def search_by_parameters(self, params: Dict) -> List[Dict]:
        """Поиск по числовым параметрам"""
        pass
    
    @abstractmethod
    def compare(self, items: List[str], criteria: List[str]) -> Dict:
        """Сравнивает элементы по критериям"""
        pass