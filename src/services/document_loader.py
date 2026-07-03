# src/services/document_loader.py

import os
import re
import csv
import zipfile
import tarfile
import tempfile
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

import pdfplumber
from docx import Document as DocxDocument
from pptx import Presentation as PptxPresentation
from openpyxl import load_workbook

try:
    import odf.opendocument
    from odf.text import P
    from odf.table import Table, TableRow, TableCell
    ODF_AVAILABLE = True
except ImportError:
    ODF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = False
except ImportError:
    OCR_AVAILABLE = False

try:
    import xlrd
    XLRD_AVAILABLE = True
except ImportError:
    XLRD_AVAILABLE = False

from src.core.interfaces import IDocumentLoader
from src.core.exceptions import DocumentLoadError
from src.models.document import Document, DocumentType
from src.utils.logger import Logger


@dataclass
class LoaderConfig:
    """Конфигурация загрузчика"""
    supported_extensions: List[str] = field(default_factory=lambda: [
        '.pdf', '.docx', '.txt', '.rtf', '.odt',
        '.pptx', '.ppt', '.odp', '.key',
        '.xlsx', '.xls', '.csv', '.ods',
        '.py', '.java', '.cpp', '.c', '.h', '.js', '.ts', '.go', '.rs',
        '.rb', '.php', '.html', '.css', '.xml', '.json', '.yaml', '.yml',
        '.toml', '.ini', '.cfg', '.conf', '.sh', '.bash', '.ps1',
        '.zip', '.tar', '.tar.gz', '.tgz', '.gz', '.bz2', '.7z',
        '.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif',
        '.md', '.rst', '.tex', '.bib'
    ])
    max_file_size_mb: int = 100
    encoding: str = 'utf-8'
    fallback_encodings: List[str] = field(default_factory=lambda: ['cp1251', 'koi8-r', 'latin1'])
    extract_images: bool = False
    extract_archives: bool = True
    max_archive_depth: int = 3
    ocr_language: str = 'rus+eng'
    max_pages_ocr: int = 10


class DocumentLoader(IDocumentLoader):
    """Загрузчик документов любых форматов"""
    
    def __init__(self, config: Optional[LoaderConfig] = None):
        self.config = config or LoaderConfig()
        self.logger = Logger(__name__)
        
        self.document_type_map = {
            'доклады': DocumentType.REPORT,
            'журналы': DocumentType.JOURNAL,
            'конференции': DocumentType.CONFERENCE,
            'обзоры': DocumentType.REVIEW,
            'статьи': DocumentType.ARTICLE,
            'патенты': DocumentType.PATENT,
            'диссертации': DocumentType.THESIS,
            'презентации': DocumentType.REPORT,
            'таблицы': DocumentType.REPORT,
            'код': DocumentType.REPORT,
            'архивы': DocumentType.REPORT
        }
        
        self._temp_dir = None
    
    def load(self, source: str) -> List[Document]:
        """Загружает документы из источника"""
        
        path = Path(source)
        
        if not path.exists():
            raise DocumentLoadError(f"Путь не существует: {source}")
        
        documents = []
        
        if path.is_file():
            doc = self.load_single(str(path))
            if doc:
                documents.append(doc)
        elif path.is_dir():
            documents = self._load_directory(path)
        else:
            raise DocumentLoadError(f"Неподдерживаемый тип источника: {source}")
        
        self.logger.info(f"Загружено {len(documents)} документов из {source}")
        return documents
    
    def load_single(self, file_path: str) -> Optional[Document]:
        """Загружает один документ любого формата"""
        
        path = Path(file_path)
        
        if not path.exists():
            self.logger.warning(f"Файл не существует: {file_path}")
            return None
        
        ext = path.suffix.lower()
        if ext not in self.config.supported_extensions:
            self.logger.debug(f"Неподдерживаемый формат: {ext}")
            return None
        
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            self.logger.warning(f"Файл слишком большой: {size_mb:.1f}MB")
            return None
        
        try:
            text, metadata_extra = self._extract_content(file_path, ext)
            
            metadata = self._extract_metadata(path.name)
            metadata.update(metadata_extra)
            
            doc_type = self._detect_document_type(path)
            
            return Document(
                name=metadata.get('title', path.stem),
                description=f"Загружен из {path.name}",
                doc_type=doc_type,
                authors=metadata.get('authors', []),
                year=metadata.get('year'),
                keywords=metadata.get('keywords', []),
                text=text,
                file_path=str(path),
                metadata=metadata
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки {path.name}: {str(e)}")
            return None
    
    def _load_directory(self, directory: Path) -> List[Document]:
        """Загружает все документы из директории рекурсивно"""
        
        documents = []
        
        total_files = 0
        supported_files = 0
        
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_files += 1
                
                ext = file_path.suffix.lower()
                if ext in self.config.supported_extensions:
                    supported_files += 1
                    
                    try:
                        doc = self.load_single(str(file_path))
                        if doc and doc.text:
                            documents.append(doc)
                    except Exception as e:
                        self.logger.error(f"Ошибка при загрузке {file_path}: {str(e)}")
                else:
                    self.logger.debug(f"Пропущен неподдерживаемый файл: {file_path}")
        
        self.logger.info(
            f"Найдено файлов: {total_files}, "
            f"поддерживаемых: {supported_files}, "
            f"загружено: {len(documents)}"
        )
        
        return documents
    
    def _extract_content(self, file_path: str, ext: str) -> Tuple[str, Dict]:
        """Извлекает контент в зависимости от формата"""
        
        text = ""
        metadata = {}
        
        try:
            if ext == '.pdf':
                text, metadata = self._extract_pdf(file_path)
            elif ext in ['.docx']:
                text, metadata = self._extract_docx(file_path)
            elif ext == '.txt':
                text, metadata = self._extract_txt(file_path)
            elif ext == '.rtf':
                text, metadata = self._extract_as_text(file_path)
            elif ext == '.odt' and ODF_AVAILABLE:
                text, metadata = self._extract_odt(file_path)
            elif ext in ['.pptx', '.ppt']:
                text, metadata = self._extract_pptx(file_path)
            elif ext == '.odp' and ODF_AVAILABLE:
                text, metadata = self._extract_odp(file_path)
            elif ext == '.key':
                text, metadata = self._extract_as_text(file_path)
            elif ext in ['.xlsx', '.xls']:
                text, metadata = self._extract_excel(file_path)
            elif ext == '.ods' and ODF_AVAILABLE:
                text, metadata = self._extract_ods(file_path)
            elif ext == '.csv':
                text, metadata = self._extract_csv(file_path)
            elif ext in ['.py', '.java', '.cpp', '.c', '.h', '.js', '.ts', '.go', 
                         '.rs', '.rb', '.php', '.sh', '.bash', '.ps1']:
                text, metadata = self._extract_code(file_path, ext)
            elif ext in ['.html', '.css', '.xml', '.json', '.yaml', '.yml', 
                         '.toml', '.ini', '.cfg', '.conf']:
                text, metadata = self._extract_structured(file_path, ext)
            elif ext in ['.md', '.rst']:
                text, metadata = self._extract_markup(file_path, ext)
            elif ext == '.tex':
                text, metadata = self._extract_tex(file_path)
            elif ext == '.bib':
                text, metadata = self._extract_bib(file_path)
            elif ext in ['.zip', '.tar', '.gz', '.bz2', '.7z']:
                text, metadata = self._extract_archive(file_path, ext)
            elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif']:
                text, metadata = self._extract_image(file_path)
            else:
                text, metadata = self._extract_as_text(file_path)
        except Exception as e:
            self.logger.warning(f"Ошибка извлечения из {file_path}: {str(e)}")
            text, metadata = self._extract_as_text(file_path)
        
        return text, metadata
    
    def _extract_pdf(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из PDF"""
        text = ""
        metadata = {}
        
        try:
            with pdfplumber.open(file_path) as pdf:
                metadata = {
                    'pages': len(pdf.pages),
                    'pdf_metadata': getattr(pdf, 'metadata', {})
                }
                
                for page in pdf.pages:
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as e:
                        self.logger.debug(f"Ошибка страницы PDF: {e}")
                
        except Exception as e:
            self.logger.error(f"Ошибка PDF: {str(e)}")
            text, _ = self._extract_as_text(file_path)
        
        return text, metadata
    
    def _extract_docx(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из DOCX"""
        text = ""
        metadata = {}
        
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header[:4] != b'PK\x03\x04':
                    self.logger.debug(f"Не DOCX файл: {file_path}, пробуем как текст")
                    return self._extract_as_text(file_path)
            
            doc = DocxDocument(file_path)
            
            for para in doc.paragraphs:
                if para.text.strip():
                    text += para.text + "\n"
            
            for table in doc.tables:
                try:
                    for row in table.rows:
                        row_text = []
                        for cell in row.cells:
                            if cell.text.strip():
                                row_text.append(cell.text.strip())
                        if row_text:
                            text += " | ".join(row_text) + "\n"
                except Exception as e:
                    self.logger.debug(f"Ошибка чтения таблицы: {e}")
            
            try:
                core_props = doc.core_properties
                metadata = {
                    'author': getattr(core_props, 'author', None),
                    'created': str(getattr(core_props, 'created', '')),
                    'modified': str(getattr(core_props, 'modified', '')),
                    'title': getattr(core_props, 'title', None),
                    'subject': getattr(core_props, 'subject', None)
                }
            except Exception:
                pass
            
        except Exception as e:
            self.logger.debug(f"Ошибка DOCX: {str(e)}, пробуем как текст")
            text, metadata = self._extract_as_text(file_path)
        
        return text, metadata
    
    def _extract_txt(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из TXT - прямое чтение с пробой кодировок"""
        text = ""
        metadata = {}
        
        encodings = ['utf-8', 'cp1251', 'koi8-r', 'latin1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    text = f.read()
                metadata = {
                    'lines': len(text.split('\n')) if text else 0,
                    'size_bytes': len(text),
                    'encoding': encoding
                }
                self.logger.debug(f"Файл {Path(file_path).name} прочитан в кодировке {encoding}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.error(f"Ошибка чтения TXT в {encoding}: {str(e)}")
                continue
        
        if not text:
            self.logger.warning(f"Не удалось прочитать файл {Path(file_path).name}")
        
        return text, metadata
    
    def _extract_pptx(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из PowerPoint"""
        text = ""
        metadata = {}
        
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                if header[:4] != b'PK\x03\x04':
                    return self._extract_as_text(file_path)
            
            prs = PptxPresentation(file_path)
            metadata = {'slides': len(prs.slides)}
            
            for i, slide in enumerate(prs.slides):
                slide_text = []
                
                for shape in slide.shapes:
                    try:
                        if hasattr(shape, "text") and shape.text:
                            slide_text.append(shape.text)
                        if hasattr(shape, "table"):
                            try:
                                for row in shape.table.rows:
                                    row_text = []
                                    for cell in row.cells:
                                        if cell.text:
                                            row_text.append(cell.text)
                                    if row_text:
                                        slide_text.append(" | ".join(row_text))
                            except Exception:
                                pass
                    except Exception:
                        pass
                
                if slide_text:
                    text += f"\n--- Слайд {i+1} ---\n"
                    text += "\n".join(slide_text) + "\n"
            
        except Exception as e:
            self.logger.debug(f"Ошибка PPTX: {str(e)}, пробуем как текст")
            text, _ = self._extract_as_text(file_path)
        
        return text, metadata
    
    def _extract_excel(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из Excel"""
        text = ""
        metadata = {}
        
        try:
            wb = load_workbook(file_path, data_only=True, read_only=True)
            
            metadata = {
                'sheets': len(wb.sheetnames),
                'sheet_names': wb.sheetnames
            }
            
            for sheet_name in wb.sheetnames[:3]:
                ws = wb[sheet_name]
                sheet_text = []
                row_count = 0
                
                for row in ws.iter_rows(values_only=True):
                    row_text = []
                    for cell in row:
                        if cell is not None:
                            row_text.append(str(cell))
                    if row_text and any(row_text):
                        sheet_text.append(" | ".join(row_text))
                        row_count += 1
                        if row_count > 100:
                            break
                
                if sheet_text:
                    text += f"\n--- Лист: {sheet_name} ---\n"
                    text += "\n".join(sheet_text) + "\n"
            
        except Exception as e:
            self.logger.debug(f"Ошибка Excel: {str(e)}, пробуем как текст")
            text, _ = self._extract_as_text(file_path)
        
        return text, metadata
    
    def _extract_csv(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из CSV"""
        text = ""
        metadata = {}
        
        try:
            encodings = [self.config.encoding] + self.config.fallback_encodings
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        
                        metadata = {
                            'rows': len(rows),
                            'columns': len(rows[0]) if rows else 0
                        }
                        
                        if rows:
                            text += " | ".join(rows[0]) + "\n"
                            text += "-" * 50 + "\n"
                        
                        for row in rows[1:101]:
                            text += " | ".join(str(cell) for cell in row) + "\n"
                        
                        if len(rows) > 101:
                            text += f"... и еще {len(rows) - 101} строк\n"
                        
                        break
                except UnicodeDecodeError:
                    continue
                
        except Exception as e:
            self.logger.debug(f"Ошибка CSV: {str(e)}")
        
        return text, metadata
    
    def _extract_code(self, file_path: str, ext: str) -> Tuple[str, Dict]:
        """Извлечение из файлов с кодом"""
        text = ""
        metadata = {}
        
        try:
            content = self._read_text_file(file_path)
            
            if not content:
                return self._extract_as_text(file_path)
            
            metadata = {
                'language': ext[1:],
                'lines': len(content.split('\n')),
                'size_bytes': len(content)
            }
            
            lines = content.split('\n')
            
            comments = []
            for line in lines[:200]:
                line_stripped = line.strip()
                if line_stripped.startswith('#') or line_stripped.startswith('//'):
                    comments.append(line_stripped)
                elif '/*' in line_stripped or '*/' in line_stripped:
                    comments.append(line_stripped)
            
            if comments:
                text = "Комментарии в коде:\n" + "\n".join(comments[:50]) + "\n"
            
            structure = self._extract_code_structure(content, ext[1:])
            if structure:
                text += "\nСтруктура кода:\n" + structure
            
            text += "\nКод (первые 50 строк):\n" + "\n".join(lines[:50])
            if len(lines) > 50:
                text += f"\n... и еще {len(lines) - 50} строк\n"
            
        except Exception as e:
            self.logger.debug(f"Ошибка извлечения кода: {str(e)}")
            text, _ = self._extract_as_text(file_path)
        
        return text, metadata
    
    def _extract_code_structure(self, content: str, language: str) -> str:
        """Извлекает структуру из кода"""
        structure = []
        
        if language == 'py':
            try:
                import ast
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        structure.append(f"Класс: {node.name}")
                    elif isinstance(node, ast.FunctionDef):
                        structure.append(f"Функция: {node.name}()")
                    elif isinstance(node, ast.AsyncFunctionDef):
                        structure.append(f"Асинхронная функция: {node.name}()")
            except:
                pass
        
        else:
            patterns = {
                'java': r'(class|interface|enum)\s+(\w+)',
                'cpp': r'(class|struct|enum)\s+(\w+)',
                'js': r'(function|class)\s+(\w+)',
                'go': r'func\s+(\w+)\s*\(',
                'rs': r'(fn|struct|enum|impl)\s+(\w+)'
            }
            
            if language in patterns:
                matches = re.findall(patterns[language], content)
                for match in matches[:20]:
                    structure.append(f"{match[0]}: {match[1]}")
        
        return "\n".join(structure[:50])
    
    def _extract_archive(self, file_path: str, ext: str) -> Tuple[str, Dict]:
        """Извлечение из архивов"""
        text = ""
        metadata = {}
        
        if not self.config.extract_archives:
            return "Архив не распакован", {'archived': True}
        
        try:
            temp_dir = tempfile.mkdtemp()
            files = []
            
            if ext == '.zip':
                with zipfile.ZipFile(file_path, 'r') as zf:
                    files = zf.namelist()
                    zf.extractall(temp_dir)
            
            elif ext in ['.tar', '.tar.gz', '.tgz', '.gz']:
                mode = 'r:gz' if ext in ['.tar.gz', '.tgz'] else 'r:'
                with tarfile.open(file_path, mode) as tf:
                    files = tf.getnames()
                    tf.extractall(temp_dir)
            
            metadata = {
                'files_count': len(files),
                'files': files[:50]
            }
            
            for fname in files[:20]:
                full_path = Path(temp_dir) / fname
                if full_path.is_file():
                    try:
                        sub_doc = self.load_single(str(full_path))
                        if sub_doc and sub_doc.text:
                            text += f"\n--- Файл в архиве: {fname} ---\n"
                            text += sub_doc.text[:1000] + "\n"
                    except Exception as e:
                        self.logger.warning(f"Не удалось прочитать {fname}: {e}")
            
            import shutil
            shutil.rmtree(temp_dir)
            
        except Exception as e:
            self.logger.error(f"Ошибка распаковки архива: {str(e)}")
            return f"Не удалось распаковать архив: {str(e)}", {'archived': True}
        
        return text, metadata
    
    def _extract_image(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение текста из изображения (OCR)"""
        if not OCR_AVAILABLE:
            return "OCR не доступен (tesseract не установлен)", {'ocr_available': False}
        
        text = ""
        metadata = {}
        
        try:
            img = Image.open(file_path)
            
            metadata = {
                'width': img.width,
                'height': img.height,
                'mode': img.mode,
                'format': img.format
            }
            
            text = self._ocr_image(img)
            
        except Exception as e:
            self.logger.debug(f"Ошибка OCR: {str(e)}")
            return f"Ошибка OCR: {str(e)}", {}
        
        return text, metadata
    
    def _ocr_image(self, image) -> str:
        """Выполняет OCR на изображении"""
        if not OCR_AVAILABLE:
            return ""
        
        try:
            config = f'--psm 6 -l {self.config.ocr_language}'
            return pytesseract.image_to_string(image, config=config)
        except Exception as e:
            return ""
    
    def _extract_structured(self, file_path: str, ext: str) -> Tuple[str, Dict]:
        """Извлечение из структурированных файлов"""
        text = ""
        metadata = {}
        
        try:
            content = self._read_text_file(file_path)
            
            if not content:
                return self._extract_as_text(file_path)
            
            metadata = {
                'format': ext[1:],
                'size_bytes': len(content),
                'lines': len(content.split('\n'))
            }
            
            lines = content.split('\n')[:100]
            text = f"Содержимое ({ext[1:]}):\n" + "\n".join(lines)
            if len(content.split('\n')) > 100:
                text += f"\n... и еще {len(content.split('\n')) - 100} строк\n"
            
        except Exception as e:
            self.logger.debug(f"Ошибка чтения: {str(e)}")
        
        return text, metadata
    
    def _extract_markup(self, file_path: str, ext: str) -> Tuple[str, Dict]:
        """Извлечение из Markdown, RST"""
        text = ""
        metadata = {}
        
        try:
            content = self._read_text_file(file_path)
            
            if not content:
                return self._extract_as_text(file_path)
            
            metadata = {
                'format': ext[1:],
                'size_bytes': len(content),
                'lines': len(content.split('\n'))
            }
            
            lines = content.split('\n')
            clean_lines = []
            
            for line in lines:
                line = re.sub(r'^#+\s+', '', line)
                line = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line)
                line = re.sub(r'[*_]{1,2}([^*_]+)[*_]{1,2}', r'\1', line)
                if not line.startswith('```') and not line.startswith('    '):
                    clean_lines.append(line)
            
            text = "\n".join(clean_lines[:200])
            
        except Exception as e:
            self.logger.debug(f"Ошибка чтения: {str(e)}")
        
        return text, metadata
    
    def _extract_tex(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из LaTeX"""
        text = ""
        metadata = {}
        
        try:
            content = self._read_text_file(file_path)
            
            if not content:
                return self._extract_as_text(file_path)
            
            metadata = {'lines': len(content.split('\n'))}
            
            lines = content.split('\n')
            clean_lines = []
            
            for line in lines:
                line = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', line)
                line = re.sub(r'\\[a-zA-Z]+', '', line)
                if line.strip() and not line.strip().startswith('%'):
                    clean_lines.append(line.strip())
            
            text = "\n".join(clean_lines[:200])
            
            structure = []
            for line in lines[:100]:
                if re.match(r'\\section\{', line):
                    structure.append(f"Раздел: {re.sub(r'\\section\{([^}]*)\}', r'\1', line)}")
                elif re.match(r'\\subsection\{', line):
                    structure.append(f"Подраздел: {re.sub(r'\\subsection\{([^}]*)\}', r'\1', line)}")
                elif re.match(r'\\chapter\{', line):
                    structure.append(f"Глава: {re.sub(r'\\chapter\{([^}]*)\}', r'\1', line)}")
            
            if structure:
                text = "Структура документа:\n" + "\n".join(structure) + "\n\n" + text
            
        except Exception as e:
            self.logger.debug(f"Ошибка чтения: {str(e)}")
        
        return text, metadata
    
    def _extract_bib(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из BibTeX"""
        text = ""
        metadata = {}
        
        try:
            content = self._read_text_file(file_path)
            
            if not content:
                return self._extract_as_text(file_path)
            
            entries = re.findall(r'@[a-zA-Z]+{', content)
            metadata = {'entries': len(entries)}
            
            entries_full = re.findall(r'@[a-zA-Z]+{[^,]+,\s*([^}]*)}', content)
            
            text = f"Найдено {len(entries_full)} библиографических записей:\n\n"
            
            for entry in entries_full[:50]:
                fields = {}
                for field in ['author', 'title', 'year', 'journal', 'booktitle']:
                    pattern = field + r'\s*=\s*{([^}]*)}'
                    match = re.search(pattern, entry)
                    if match:
                        fields[field] = match.group(1)
                
                if fields:
                    text += f"* {fields.get('author', 'Без автора')}: {fields.get('title', 'Без названия')}"
                    if fields.get('year'):
                        text += f" ({fields['year']})"
                    text += "\n"
            
        except Exception as e:
            self.logger.debug(f"Ошибка чтения: {str(e)}")
        
        return text, metadata
    
    def _extract_odt(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из ODT"""
        text = ""
        metadata = {}
        
        try:
            doc = odf.opendocument.load(file_path)
            paragraphs = doc.getElementsByType(P)
            
            for para in paragraphs:
                para_text = []
                for node in para.childNodes:
                    if hasattr(node, 'data') and node.data:
                        para_text.append(node.data.strip())
                if para_text:
                    text += " ".join(para_text) + "\n"
            
            tables = doc.getElementsByType(Table)
            for table in tables:
                for row in table.getElementsByType(TableRow):
                    row_text = []
                    for cell in row.getElementsByType(TableCell):
                        cell_text = []
                        for para in cell.getElementsByType(P):
                            for node in para.childNodes:
                                if hasattr(node, 'data') and node.data:
                                    cell_text.append(node.data.strip())
                        if cell_text:
                            row_text.append(" ".join(cell_text))
                    if row_text:
                        text += " | ".join(row_text) + "\n"
            
        except Exception as e:
            self.logger.debug(f"Ошибка ODT: {str(e)}")
        
        return text, metadata
    
    def _extract_odp(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из ODP"""
        text = ""
        metadata = {}
        
        try:
            doc = odf.opendocument.load(file_path)
            paragraphs = doc.getElementsByType(P)
            
            for para in paragraphs:
                para_text = []
                for node in para.childNodes:
                    if hasattr(node, 'data') and node.data:
                        para_text.append(node.data.strip())
                if para_text:
                    text += " ".join(para_text) + "\n"
            
        except Exception as e:
            self.logger.debug(f"Ошибка ODP: {str(e)}")
        
        return text, metadata
    
    def _extract_ods(self, file_path: str) -> Tuple[str, Dict]:
        """Извлечение из ODS"""
        text = ""
        metadata = {}
        
        try:
            doc = odf.opendocument.load(file_path)
            tables = doc.getElementsByType(Table)
            
            for table in tables:
                for row in table.getElementsByType(TableRow):
                    row_text = []
                    for cell in row.getElementsByType(TableCell):
                        cell_text = []
                        for para in cell.getElementsByType(P):
                            for node in para.childNodes:
                                if hasattr(node, 'data') and node.data:
                                    cell_text.append(node.data.strip())
                        if cell_text:
                            row_text.append(" ".join(cell_text))
                    if row_text:
                        text += " | ".join(row_text) + "\n"
            
        except Exception as e:
            self.logger.debug(f"Ошибка ODS: {str(e)}")
        
        return text, metadata
    
    def _extract_as_text(self, file_path: str) -> Tuple[str, Dict]:
        """Пытается прочитать файл как текст"""
        text = ""
        metadata = {'format': 'text'}
        
        encodings = [self.config.encoding] + self.config.fallback_encodings
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    metadata['lines'] = len(content.split('\n'))
                    text = content[:10000]
                    if len(content) > 10000:
                        text += f"\n... и еще {len(content) - 10000} символов\n"
                    break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                continue
        
        return text, metadata
    
    def _read_text_file(self, file_path: str) -> str:
        """Читает текстовый файл с попыткой разных кодировок"""
        encodings = [self.config.encoding] + self.config.fallback_encodings
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception:
                continue
        
        return ""
    
    def _extract_metadata(self, filename: str) -> Dict[str, Any]:
        """Извлекает метаданные из имени файла"""
        
        metadata = {
            'title': filename,
            'authors': [],
            'year': None,
            'keywords': []
        }
        
        year_match = re.search(r'20\d{2}', filename)
        if year_match:
            metadata['year'] = int(year_match.group())
        
        author_match = re.search(r'([А-Я][а-я]+_[А-Я]\.)', filename)
        if author_match:
            metadata['authors'].append(author_match.group(1))
        
        name = Path(filename).stem
        parts = re.split(r'[_\-\.\s]+', name)
        keywords = [p for p in parts if len(p) > 3 and not p.isdigit()]
        if keywords:
            metadata['keywords'] = keywords[:5]
        
        if keywords:
            metadata['title'] = ' '.join(keywords[:3])
        
        return metadata
    
    def _detect_document_type(self, path: Path) -> DocumentType:
        """Определяет тип документа по пути"""
        
        for parent in path.parents:
            for folder_name, doc_type in self.document_type_map.items():
                if folder_name in str(parent):
                    return doc_type
        
        ext = path.suffix.lower()
        if ext in ['.pptx', '.ppt', '.odp', '.key']:
            return DocumentType.REPORT
        elif ext in ['.xlsx', '.xls', '.csv', '.ods']:
            return DocumentType.REPORT
        elif ext in ['.py', '.java', '.cpp', '.c', '.js', '.ts', '.go']:
            return DocumentType.REPORT
        else:
            return DocumentType.ARTICLE