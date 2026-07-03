# main.py

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any

from src.core.exceptions import KnowledgeGraphError
from src.services.document_loader import DocumentLoader
from src.services.ai_service import YandexAIService, AIConfig
from src.services.entity_extractor import EntityExtractor
from src.services.graph_builder import GraphBuilder
from src.repositories.neo4j_repository import Neo4jRepository
from src.utils.logger import Logger
from src.utils.config import Config


class KnowledgeGraphApplication:
    """Главное приложение Карты знаний"""
    
    def __init__(self):
        self.logger = Logger("app")
        self.config = Config()
        
        try:
            self.config.validate()
        except Exception as e:
            self.logger.warning(f"Ошибка конфигурации: {e}")
        
        self.document_loader = DocumentLoader()
        
        # AI с правильной конфигурацией
        ai_config = AIConfig(
            temperature=0.3,
            max_tokens=2000
        )
        self.ai_service = YandexAIService(ai_config)
        self.entity_extractor = EntityExtractor(self.ai_service)
        
        self.repository = None
        self.graph_builder = None
        try:
            self.repository = Neo4jRepository()
            self.graph_builder = GraphBuilder(self.repository)
        except Exception as e:
            self.logger.warning(f"Neo4j не доступен: {e}")
            self.graph_builder = None
    
    def load_documents(self, source_dir: str = None) -> List:
        """Загружает документы из директории с индикацией прогресса"""
        
        source = source_dir or Config.RAW_DATA_DIR
        
        self.logger.info(f"Загрузка документов из: {source}")
        
        if not os.path.exists(source):
            self.logger.warning(f"Директория не существует: {source}")
            return []
        
        total_files = 0
        for root, dirs, files in os.walk(source):
            total_files += len(files)
        
        self.logger.info(f"Найдено {total_files} файлов в директории")
        
        if total_files == 0:
            return []
        
        documents = []
        processed = 0
        
        for root, dirs, files in os.walk(source):
            for file in files:
                processed += 1
                file_path = os.path.join(root, file)
                
                if processed % 10 == 0 or processed == total_files:
                    self.logger.info(f"Прогресс загрузки: {processed}/{total_files} файлов ({int(processed/total_files*100)}%)")
                
                try:
                    doc = self.document_loader.load_single(file_path)
                    if doc and doc.text:
                        documents.append(doc)
                except Exception as e:
                    self.logger.debug(f"Ошибка загрузки {file}: {e}")
        
        self.logger.info(f"Загружено {len(documents)} документов из {total_files} файлов")
        return documents
    
    def process_documents(self, documents: List) -> List[Dict[str, Any]]:
        """Обрабатывает документы с индикацией прогресса"""
        
        self.logger.info(f"Начало обработки {len(documents)} документов")
        
        from src.models.document import Document
        doc_objects = []
        for doc_data in documents:
            if isinstance(doc_data, Document):
                doc_objects.append(doc_data)
            elif isinstance(doc_data, dict):
                doc_objects.append(Document.from_dict(doc_data))
        
        valid_docs = [doc for doc in doc_objects if doc.text and len(doc.text.strip()) > 20]
        
        if len(valid_docs) < len(doc_objects):
            self.logger.warning(f"Пропущено {len(doc_objects) - len(valid_docs)} документов с коротким текстом")
        
        results = []
        total = len(valid_docs)
        
        for i, doc in enumerate(valid_docs):
            self.logger.info(f"Обработка {i+1}/{total}: {doc.name[:50]}... ({int((i+1)/total*100)}%)")
            
            try:
                entities = self.ai_service.extract_entities(doc.text)
                
                if "error" in entities:
                    self.logger.warning(f"Ошибка извлечения для {doc.name}: {entities.get('error')}")
                    results.append({
                        "doc_id": doc.id,
                        "doc_name": doc.name,
                        "status": "error",
                        "error": entities.get('error')
                    })
                else:
                    results.append({
                        "doc_id": doc.id,
                        "doc_name": doc.name,
                        "status": "success",
                        "entities": entities
                    })
                    self.logger.info(f"Успешно обработан: {doc.name[:40]}")
                    
            except Exception as e:
                self.logger.error(f"Ошибка обработки {doc.name}: {str(e)}")
                results.append({
                    "doc_id": doc.id,
                    "doc_name": doc.name,
                    "status": "error",
                    "error": str(e)
                })
        
        self.logger.info(f"Обработано {len(results)} документов")
        return results
    
    def build_knowledge_graph(self, extracted_data: List[Dict[str, Any]]):
        """Строит граф знаний из извлеченных данных"""
        
        if not self.graph_builder:
            self.logger.warning("Граф не доступен (Neo4j не запущен)")
            return None
        
        successful = [d for d in extracted_data if d.get('status') == 'success']
        
        if not successful:
            self.logger.warning("Нет успешно извлеченных данных для построения графа")
            return {"error": "Нет данных"}
        
        self.logger.info(f"Построение графа из {len(successful)} документов")
        self.graph_builder.build_from_documents(successful)
        
        stats = self.graph_builder.get_statistics()
        self.logger.info(f"Статистика графа: {stats}")
        
        return stats
    
    def run_pipeline(self, source_dir: str = None):
        """Запускает полный пайплайн обработки"""
        
        try:
            self.logger.info("=" * 60)
            self.logger.info("Запуск пайплайна Карты знаний")
            self.logger.info("=" * 60)
            
            start_time = time.time()
            
            documents = self.load_documents(source_dir)
            if not documents:
                self.logger.warning("Нет документов для обработки")
                return
            
            extracted = self.process_documents(documents)
            
            output_file = Path(Config.PROCESSED_DATA_DIR) / "extracted_data.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(extracted, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Результаты сохранены в {output_file}")
            
            if self.graph_builder:
                stats = self.build_knowledge_graph(extracted)
            else:
                stats = {"error": "Neo4j не доступен"}
                self.logger.warning("Граф не построен: Neo4j не запущен")
            
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = int(elapsed_time % 60)
            
            self.logger.info("=" * 60)
            self.logger.info(f"Пайплайн завершен за {minutes}м {seconds}с")
            self.logger.info(f"Обработано документов: {len(documents)}")
            
            successful = len([d for d in extracted if d.get('status') == 'success'])
            self.logger.info(f"Успешно обработано: {successful} из {len(extracted)}")
            self.logger.info(f"Статистика графа: {stats}")
            self.logger.info("=" * 60)
            
            return {
                "documents_processed": len(documents),
                "successful": successful,
                "extracted_data": extracted,
                "graph_stats": stats,
                "elapsed_time": f"{minutes}м {seconds}с"
            }
            
        except KnowledgeGraphError as e:
            self.logger.error(f"Ошибка пайплайна: {str(e)}")
            raise
        except Exception as e:
            self.logger.critical(f"Неожиданная ошибка: {str(e)}")
            raise
    
    def cleanup(self):
        """Очистка ресурсов"""
        if self.repository:
            try:
                self.repository.close()
            except:
                pass
        self.logger.info("Ресурсы освобождены")


def main():
    """Точка входа"""
    
    app = KnowledgeGraphApplication()
    
    try:
        result = app.run_pipeline()
        print("\n" + "=" * 60)
        print("Проект Карта знаний R&D выполнен")
        print(f"Обработано документов: {result['documents_processed']}")
        print(f"Успешно обработано: {result['successful']}")
        print(f"Время выполнения: {result['elapsed_time']}")
        print(f"Статистика графа: {result.get('graph_stats', 'Не доступна')}")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        return 1
    except Exception as e:
        print(f"\nОшибка: {str(e)}")
        return 1
    finally:
        app.cleanup()
    
    return 0


if __name__ == "__main__":
    exit(main())