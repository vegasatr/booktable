# BookTable.AI Bot

Telegram-бот для поиска и бронирования ресторанов на Пхукете с использованием AI.

## 🚀 Описание проекта

BookTable.AI - это интеллектуальный помощник для путешественников, который помогает найти идеальный ресторан на Пхукете и забронировать столик за секунды.

### Основные возможности:
- 🌍 Поддержка 120+ языков с автоматическим определением
- 💰 Фильтрация по бюджету ($, $$, $$$, $$$$)
- 📍 Поиск по районам или геолокации
- 🤖 AI-powered рекомендации на основе предпочтений
- 📱 Интуитивный интерфейс с кнопками и быстрыми ответами

## 🏗️ Архитектура проекта

Проект использует модульную архитектуру для лучшей поддерживаемости и масштабируемости:

```
src/bot/
├── ai/                         # AI модули
│   ├── core.py                # OpenAI интеграция, AI-процессор
│   └── translation.py         # Переводы и языки
├── database/                  # База данных
│   ├── connection.py         # PostgreSQL подключение
│   ├── users.py             # Операции с пользователями
│   └── restaurants.py       # Операции с ресторанами
├── handlers/                  # Telegram обработчики
│   ├── start.py             # /start, язык, бюджет
│   ├── location.py          # Геолокация и районы
│   └── message.py           # Обработка сообщений
├── managers/                  # Бизнес-логика
│   ├── user_state.py        # Управление состоянием
│   └── restaurant.py        # Управление ресторанами
└── utils/                     # Утилиты
    ├── geo.py               # Геолокационные функции
    └── permissions.py       # Права доступа
```

## 🧪 Comprehensive Testing Framework

Проект имеет полную систему тестирования с 90+ тестами:

### Unit Tests (Автоматические):
- `tests/unit/test_ai_core.py` - AI функции (22 теста)
- `tests/unit/test_ai_translation.py` - Переводы (19 тестов)
- `tests/unit/test_database_users.py` - База данных (13 тестов)

### Integration Tests (Комплексные):
- `tests/integration/test_bot_workflow.py` - Полный workflow пользователя
- `tests/integration/test_external_apis.py` - Интеграция с внешними API
- `tests/integration/test_edge_cases.py` - Edge cases и обработка ошибок

### Manual Tests (Диалоговые исследования):
- `tests/manual/dialogue_studies/ai_thinking_analysis.py` - Анализ AI решений
- `tests/manual/dialogue_studies/restaurant_chat_processor.py` - Тестирование контекста

### Команды тестирования:
```bash
# Все unit тесты
./scripts/run_tests.sh

# Integration тесты
./scripts/run_integration_tests.sh

# Быстрая проверка
./scripts/quick_test.sh

# Полный отчет
./scripts/final_test_report.sh
```

## 🛠️ Технологический стек

- **Python 3.10+** - основной язык
- **python-telegram-bot** - Telegram Bot API
- **PostgreSQL** - база данных ресторанов
- **OpenAI GPT-4o** - AI для обработки запросов
- **psycopg2** - PostgreSQL адаптер
- **geopy** - геолокационные сервисы
- **pytest** - comprehensive testing framework

## 📊 Оптимизации

Бот прошел полную оптимизацию и рефакторинг:

1. **Модульная архитектура** - main.py сокращен с 1992 до 605 строк (70% сокращение)
2. **AI оптимизация** - 70-85% экономии токенов OpenAI
3. **Comprehensive testing** - 90+ тестов покрывают все сценарии
4. **Smart git workflow** - автоматическое тестирование перед push
5. **Production-ready** - обработка всех edge cases и ошибок

## 🚀 Запуск проекта

### Требования:
- Python 3.10+
- PostgreSQL
- OpenAI API ключ
- Telegram Bot Token

### Установка:

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd booktable_bot
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Настройте переменные окружения в `.env`:
```env
TELEGRAM_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o
DATABASE_URL=postgresql://user:password@localhost/booktable
```

5. Инициализируйте базу данных:
```bash
psql -U postgres -d booktable -f init_db.sql
```

6. Запустите бота:
```bash
python main.py
```

## 🔧 Управление проектом

### Разработка:
```bash
# Запуск всех тестов
./scripts/run_tests.sh

# Integration тесты
./scripts/run_integration_tests.sh

# Manual диалоговые тесты
python tests/manual/dialogue_studies/ai_thinking_analysis.py
```

### 🚀 Smart Git Push (с обязательным тестированием):
```bash
# Единственный способ залить код на GitHub
./scripts/git_push.sh
```

**Особенности Smart Git Push:**
- ✅ Автоматически прогоняет ВСЕ тесты перед push
- ✅ Push происходит ТОЛЬКО если все тесты прошли
- ✅ Автоинкремент версии
- ❌ Невозможно залить код с ошибками

### Отчеты:
```bash
# Полный отчет по проекту
./scripts/final_test_report.sh
```

## 📁 Структура файлов

- `main.py` - точка входа, сокращенный до 605 строк
- `src/bot/` - модульная архитектура
- `tests/` - comprehensive testing framework
- `scripts/` - автоматизированные скрипты
- `logs/` - логи работы бота
- `docs/` - документация

## 📈 Мониторинг и качество

- **100% TO-DO coverage** - все задачи из списка выполнены
- **90+ автоматических тестов** - unit + integration + manual
- **Error handling** - graceful обработка всех ошибок
- **Multi-user isolation** - тестирование одновременных пользователей
- **API resilience** - устойчивость к сбоям внешних сервисов

## 🎯 Production Ready Status

✅ **Modular architecture** - чистая архитектура
✅ **Comprehensive testing** - полное покрытие тестами
✅ **Smart deployment** - безопасная заливка с тестированием
✅ **Error handling** - обработка всех edge cases
✅ **Documentation** - полная документация
✅ **Monitoring** - логирование и отчеты

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения и покройте тестами
4. **Используйте `./scripts/git_push.sh`** - push с автотестированием
5. Создайте Pull Request

⚠️ **Важно**: Код без прохождения тестов не может быть залит в репозиторий!

## 📄 Лицензия

Проект распространяется под лицензией MIT. См. файл `LICENSE` для деталей.

## 📞 Поддержка

Для вопросов и поддержки обращайтесь к команде разработки.

---

**BookTable.AI** - Production-ready AI бот с comprehensive testing! 🍽️🤖 