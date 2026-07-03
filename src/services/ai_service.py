# src/services/ai_service.py

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv
import openai

from src.core.interfaces import IAService
from src.core.exceptions import AIServiceError
from src.utils.logger import Logger

load_dotenv()


@dataclass
class AIConfig:
    """Конфигурация AI сервиса"""
    api_key: str = os.getenv("YANDEX_API_KEY")
    folder_id: str = os.getenv("YANDEX_FOLDER_ID")
    model: str = os.getenv("YANDEX_MODEL", "aliceai-llm")
    base_url: str = "https://ai.api.cloud.yandex.net/v1"
    temperature: float = 0.3
    max_tokens: int = 2000


class YandexAIService(IAService):
    """Сервис для работы с Yandex AI через OpenAI-совместимый API"""
    
    def __init__(self, config: Optional[AIConfig] = None):
        self.config = config or AIConfig()
        self.logger = Logger(__name__)
        
        if not self.config.api_key or not self.config.folder_id:
            raise AIServiceError(
                "API_KEY и FOLDER_ID должны быть установлены в .env файле"
            )
        
        self.client = openai.OpenAI(
            api_key=self.config.api_key,
            project=self.config.folder_id,
            base_url=self.config.base_url
        )
        
        self.logger.info(f"Yandex AI клиент инициализирован с моделью {self.config.model}")
    
    def _make_request(self, messages: List[Dict[str, str]], instructions: str = "") -> str:
        """Выполняет запрос к AI через Responses API"""
        
        try:
            response = self.client.responses.create(
                model=f"gpt://{self.config.folder_id}/{self.config.model}",
                temperature=self.config.temperature,
                instructions=instructions,
                input=messages,
                max_output_tokens=self.config.max_tokens
            )
            
            return response.output_text
            
        except Exception as e:
            raise AIServiceError(f"Ошибка AI запроса: {str(e)}")
    
    def generate_response(self, prompt: str, context: Optional[str] = None) -> str:
        """Генерирует ответ на запрос"""
        
        messages = []
        
        if context:
            messages.append({
                "role": "system",
                "content": f"Контекст для ответа: {context}"
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        instructions = "Ты - эксперт по горно-металлургическим процессам и исследованиям. Отвечай точно, используя числовые данные. Если данных недостаточно - честно сообщи об этом."
        
        return self._make_request(messages, instructions)
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Извлекает сущности из текста с помощью AI"""
        
        if not text or len(text.strip()) < 20:
            self.logger.warning(f"Текст слишком короткий: {len(text)} символов")
            return {"error": "Текст слишком короткий"}
        
        if len(text) > 8000:
            text = text[:8000]
        
        self.logger.info(f"Отправка текста длиной {len(text)} символов")
        
        instructions = """
        Ты - специалист по извлечению информации из текстов в области металлургии.
        Извлекай сущности строго в формате JSON.
        """
        
        messages = [
            {
                "role": "user",
                "content": f"""
                Проанализируй текст и извлеки сущности в формате JSON:
                
                {text}
                
                Верни ТОЛЬКО JSON со структурой:
                {{
                    "materials": [{{"name": "", "formula": "", "properties": {{"концентрация": {{"value": 0, "unit": "мг/л"}}}}}}],
                    "processes": [{{"name": "", "type": "гидрометаллургия|пирометаллургия|экология", "parameters": {{}}}}],
                    "experiments": [{{"name": "", "conditions": "", "results": ""}}],
                    "equipment": [{{"name": "", "type": ""}}],
                    "location": "Россия|Зарубежье",
                    "year": 0,
                    "keywords": []
                }}
                """
            }
        ]
        
        try:
            response = self._make_request(messages, instructions)
            
            if not response:
                return {"error": "Пустой ответ от AI"}
            
            try:
                start = response.find('{')
                end = response.rfind('}') + 1
                
                if start != -1 and end != -1:
                    json_str = response[start:end]
                    return json.loads(json_str)
                else:
                    return {"error": "JSON не найден", "raw_response": response[:200]}
                    
            except json.JSONDecodeError as e:
                return {"error": f"Ошибка парсинга JSON", "raw_response": response[:200]}
                
        except AIServiceError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Неожиданная ошибка: {str(e)}"}
    
    def extract_batch(self, documents: List) -> List[Dict[str, Any]]:
        """Извлекает сущности из нескольких документов"""
        
        results = []
        total = len(documents)
        
        for i, doc in enumerate(documents):
            self.logger.info(f"Обработка {i+1}/{total}: {doc.name[:40]}...")
            
            try:
                if not doc.text or len(doc.text.strip()) < 20:
                    results.append({
                        "doc_id": doc.id,
                        "doc_name": doc.name,
                        "error": "Текст слишком короткий"
                    })
                    continue
                
                entities = self.extract_entities(doc.text)
                
                if "error" in entities:
                    results.append({
                        "doc_id": doc.id,
                        "doc_name": doc.name,
                        "error": entities['error']
                    })
                else:
                    results.append({
                        "doc_id": doc.id,
                        "doc_name": doc.name,
                        "entities": entities,
                        "status": "success"
                    })
                    
            except Exception as e:
                self.logger.error(f"Ошибка обработки {doc.name}: {str(e)}")
                results.append({
                    "doc_id": doc.id,
                    "doc_name": doc.name,
                    "error": str(e)
                })
        
        return results
    
    def summarize(self, texts: List[str]) -> str:
        """Создает суммаризацию текстов"""
        
        if not texts:
            return "Нет текстов для суммаризации"
        
        combined = "\n---\n".join(texts[:3])
        if len(combined) > 8000:
            combined = combined[:8000]
        
        instructions = "Ты - научный аналитик в области металлургии."
        
        messages = [
            {
                "role": "user",
                "content": f"""
                Проанализируй следующие исследования и создай структурированный обзор:
                
                {combined}
                
                Укажи:
                1. Основные выводы (консенсус)
                2. Противоречия и разногласия
                3. Пробелы в знаниях
                4. Практические рекомендации
                """
            }
        ]
        
        return self._make_request(messages, instructions)