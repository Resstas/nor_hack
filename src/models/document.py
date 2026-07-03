from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
from src.core.base import BaseEntity, Named, Temporal, Identifiable


class DocumentType(Enum):
    """Типы документов"""
    REPORT = "report"
    JOURNAL = "journal"
    CONFERENCE = "conference"
    REVIEW = "review"
    ARTICLE = "article"
    PATENT = "patent"
    THESIS = "thesis"


@dataclass
class Document(BaseEntity, Named, Temporal, Identifiable):
    """Модель документа"""
    
    doc_type: DocumentType = DocumentType.ARTICLE
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    organization: Optional[str] = None
    language: str = "ru"
    text: str = ""
    file_path: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.name,
            "description": self.description,
            "type": self.doc_type.value,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "organization": self.organization,
            "language": self.language,
            "text": self.text[:500] + "..." if len(self.text) > 500 else self.text,
            "keywords": self.keywords,
            "references": self.references,
            "file_path": self.file_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        return cls(
            id=data.get("id"),
            name=data.get("title", ""),
            description=data.get("description", ""),
            doc_type=DocumentType(data.get("type", "article")),
            authors=data.get("authors", []),
            year=data.get("year"),
            journal=data.get("journal"),
            organization=data.get("organization"),
            language=data.get("language", "ru"),
            text=data.get("text", ""),
            file_path=data.get("file_path"),
            keywords=data.get("keywords", []),
            references=data.get("references", [])
        )
    
    def get_summary(self, max_length: int = 200) -> str:
        """Возвращает краткое содержание"""
        if len(self.text) <= max_length:
            return self.text
        return self.text[:max_length] + "..."