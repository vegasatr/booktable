"""
Конфигурация приложения
"""
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Читаем версию
with open('version.txt', 'r') as f:
    VERSION = f.read().strip()

# Токены и API ключи
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o') 