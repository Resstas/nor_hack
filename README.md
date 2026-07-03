# Карта знаний R&D для горно-металлургической отрасли

## Быстрый старт

```bash
# Клонирование репозитория
git clone https://github.com/Resstas/nor_hack.git
cd nor_hack

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env, укажите свои YANDEX_FOLDER_ID, YANDEX_API_KEY, NEO4J_PASSWORD

# Запуск Neo4j (Docker)
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest

# Генерация тестовых данных или скачайте проект с яндекса диска с большим объёмом данных
python generate_test_data.py

# Запуск пайплайна обработки
python main.py

# Запуск веб-интерфейса
streamlit run src/ui/streamlit_app.py
