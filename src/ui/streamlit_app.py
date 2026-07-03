import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, List, Dict

from src.services.ai_service import YandexAIService
from src.services.entity_extractor import EntityExtractor
from src.repositories.neo4j_repository import Neo4jRepository
from src.utils.logger import Logger
from src.utils.config import Config


class StreamlitApp:
    """Streamlit интерфейс для Карты знаний"""
    
    def __init__(self):
        self.logger = Logger("ui")
        self.config = Config()
        self.ai_service = YandexAIService()
        self.entity_extractor = EntityExtractor(self.ai_service)
        self.repository = Neo4jRepository()
        
        st.set_page_config(
            page_title="Карта знаний R&D Металлургия",
            page_icon="",
            layout="wide"
        )
    
    def render(self):
        """Рендерит интерфейс"""
        
        st.title("Карта знаний горно-металлургических исследований")
        st.caption("Система управления знаниями с использованием Yandex AI Studio")
        
        with st.sidebar:
            self._render_sidebar()
        
        tabs = st.tabs([
            "Поиск",
            "Извлечение",
            "Аналитика",
            "Граф",
            "Отчеты"
        ])
        
        with tabs[0]:
            self._render_search()
        
        with tabs[1]:
            self._render_extraction()
        
        with tabs[2]:
            self._render_analytics()
        
        with tabs[3]:
            self._render_graph()
        
        with tabs[4]:
            self._render_reports()
    
    def _render_sidebar(self):
        """Рендерит боковую панель"""
        
        st.header("Настройки")
        
        st.subheader("Фильтры")
        
        search_type = st.selectbox(
            "Тип поиска",
            ["Все", "Материалы", "Процессы", "Эксперименты", "Публикации"]
        )
        st.session_state['search_type'] = search_type
        
        col1, col2 = st.columns(2)
        with col1:
            year_from = st.number_input("Год от", 2000, 2025, 2020)
        with col2:
            year_to = st.number_input("Год до", 2000, 2025, 2025)
        
        st.session_state['year_from'] = year_from
        st.session_state['year_to'] = year_to
        
        location = st.selectbox(
            "География",
            ["Все", "Россия", "Зарубежье"]
        )
        st.session_state['location'] = location
        
        if st.button("Найти", type="primary"):
            st.session_state['search_triggered'] = True
    
    def _render_search(self):
        """Рендерит вкладку поиска"""
        
        st.subheader("Поиск по базе знаний")
        
        query = st.text_input(
            "Введите запрос:",
            placeholder="например: очистка шахтных вод от сульфатов"
        )
        
        if query or st.session_state.get('search_triggered'):
            with st.spinner("Поиск..."):
                results = self._perform_search(query)
                
                if results:
                    st.success(f"Найдено {len(results)} результатов")
                    
                    for result in results:
                        with st.expander(f"{result.get('name', 'Результат')}"):
                            st.json(result)
                else:
                    st.info("Ничего не найдено")
    
    def _render_extraction(self):
        """Рендерит вкладку извлечения"""
        
        st.subheader("Извлечение сущностей из текста")
        
        text_input = st.text_area(
            "Введите текст для анализа:",
            height=200,
            placeholder="Вставьте текст документа для извлечения сущностей..."
        )
        
        if st.button("Извлечь", type="primary"):
            if text_input:
                with st.spinner("Yandex AI анализирует..."):
                    result = self.entity_extractor.extract(text_input)
                    
                    if result.get('status') == 'success':
                        entities = result.get('entities', [])
                        
                        st.success(f"Извлечено {len(entities)} сущностей")
                        
                        materials = [e for e in entities if e.entity_type.value == 'material']
                        processes = [e for e in entities if e.entity_type.value == 'process']
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Материалы:**")
                            for mat in materials:
                                st.write(f"* {mat.name}")
                                if mat.properties:
                                    st.write(f"  - {mat.properties}")
                        
                        with col2:
                            st.markdown("**Процессы:**")
                            for proc in processes:
                                st.write(f"* {proc.name}")
                                if proc.parameters:
                                    st.write(f"  - {proc.parameters}")
                        
                        with st.expander("Полный JSON"):
                            st.json(result)
                    else:
                        st.error(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
            else:
                st.warning("Введите текст для анализа")
    
    def _render_analytics(self):
        """Рендерит вкладку аналитики"""
        
        st.subheader("Аналитика и метрики")
        
        try:
            stats = self._get_graph_stats()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Публикации", stats.get('publication', 0))
            with col2:
                st.metric("Эксперименты", stats.get('experiment', 0))
            with col3:
                st.metric("Материалы", stats.get('material', 0))
            with col4:
                st.metric("Процессы", stats.get('process', 0))
            
        except Exception as e:
            st.warning("Нет данных в графе")
        
        st.subheader("Покрытие знаний по темам")
        
        topics = ["Гидрометаллургия", "Пирометаллургия", "Экология", "Переработка отходов"]
        coverage = [85, 72, 63, 41]
        
        fig = go.Figure(data=[go.Bar(
            x=topics,
            y=coverage,
            marker_color=['#2ecc71', '#3498db', '#f39c12', '#e74c3c']
        )])
        fig.update_layout(
            title="Покрытие исследований (%)",
            yaxis_range=[0, 100],
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_graph(self):
        """Рендерит вкладку графа"""
        
        st.subheader("Визуализация графа знаний")
        
        fig = go.Figure()
        
        nodes = ["Очистка воды", "Электроэкстракция", "Сульфаты", "Никель"]
        
        pos = {
            "Очистка воды": (0, 0),
            "Электроэкстракция": (2, 0),
            "Сульфаты": (0, 1),
            "Никель": (2, 1)
        }
        
        edges = [
            ("Очистка воды", "Сульфаты"),
            ("Электроэкстракция", "Никель")
        ]
        
        for edge in edges:
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            fig.add_trace(go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=2, color='#7f8c8d'),
                hoverinfo='none'
            ))
        
        for node, (x, y) in pos.items():
            fig.add_trace(go.Scatter(
                x=[x],
                y=[y],
                mode='markers+text',
                marker=dict(size=30, color='#3498db'),
                text=[node],
                textposition="middle center",
                hoverinfo='text'
            ))
        
        fig.update_layout(
            showlegend=False,
            height=500,
            xaxis=dict(showgrid=False, zeroline=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False, visible=False)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_reports(self):
        """Рендерит вкладку отчетов"""
        
        st.subheader("Генерация отчетов")
        
        report_type = st.selectbox(
            "Тип отчета",
            ["Литературный обзор", "Сравнительный анализ", "Выявление пробелов"]
        )
        
        topic = st.text_input("Тема отчета:")
        
        if st.button("Сгенерировать отчет", type="primary"):
            if topic:
                with st.spinner("Yandex AI генерирует отчет..."):
                    report = self._generate_report(topic, report_type)
                    st.markdown(report)
                    
                    st.download_button(
                        "Скачать отчет (Markdown)",
                        report,
                        file_name=f"report_{topic[:20]}.md"
                    )
            else:
                st.warning("Введите тему отчета")
    
    def _perform_search(self, query: str) -> List[Dict]:
        """Выполняет поиск"""
        return []
    
    def _get_graph_stats(self) -> Dict:
        """Получает статистику графа"""
        try:
            return self.repository.query("""
                MATCH (n)
                RETURN n.entity_type as type, count(n) as count
            """)
        except:
            return {}
    
    def _generate_report(self, topic: str, report_type: str) -> str:
        """Генерирует отчет с помощью Yandex AI"""
        
        prompt = f"""
        Сгенерируй {report_type.lower()} по теме: {topic}
        
        Включи:
        1. Основные выводы
        2. Ключевые источники
        3. Числовые данные
        4. Противоречия (если есть)
        5. Рекомендации
        """
        
        return self.ai_service.generate_response(prompt)


def run_app():
    """Запускает Streamlit приложение"""
    app = StreamlitApp()
    app.render()


if __name__ == "__main__":
    run_app()