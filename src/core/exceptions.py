class KnowledgeGraphError(Exception):
    """Базовое исключение для графа знаний"""
    pass


class DocumentLoadError(KnowledgeGraphError):
    """Ошибка загрузки документа"""
    pass


class EntityExtractionError(KnowledgeGraphError):
    """Ошибка извлечения сущностей"""
    pass


class GraphStorageError(KnowledgeGraphError):
    """Ошибка сохранения в граф"""
    pass


class AIServiceError(KnowledgeGraphError):
    """Ошибка AI сервиса"""
    pass


class ValidationError(KnowledgeGraphError):
    """Ошибка валидации данных"""
    pass