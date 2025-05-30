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

## 🗄️ Тестовая база данных ⚠️ ВАЖНО

**ВСЕГДА используйте тестовую базу для разработки и тестирования!**

### Структура баз данных:
- **`booktable`** - 🚨 ПРОДАКШН база (НЕ ТРОГАТЬ для тестов!)
- **`booktable_test`** - 🧪 Тестовая база (используйте для всех тестов)

### Создание тестовой БД:
```bash
# Создать тестовую БД с тестовыми данными
sudo scripts/create_test_db.sh

# Проверить статус
sudo -u postgres psql -d booktable_test -c "SELECT COUNT(*) FROM restaurants;"

# Удалить при необходимости
sudo -u postgres dropdb booktable_test
```

### 🚨 ПРАВИЛА БЕЗОПАСНОСТИ:
1. **НИКОГДА** не запускайте тесты на продакшн базе `booktable`
2. **ВСЕГДА** используйте `booktable_test` для:
   - Юнит тестов
   - Интеграционных тестов
   - Ручных тестов
   - Разработки новых функций
3. **АВТОМАТИЧЕСКИ** патчите connection.py в тестах на тестовую БД
4. **ОБЯЗАТЕЛЬНО** синхронизируйте изменения структуры между базами

### Тестовые данные:
- 3 тестовых пользователя (EN/RU/JP)
- 5 тестовых ресторанов
- 3 тестовых бронирования
- Полная структура как в продакшне

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
- PostgreSQL (продакшн и тестовая БД)
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
# Продакшн база (только для первичной настройки)
psql -U postgres -d booktable -f init_db.sql

# 🧪 ОБЯЗАТЕЛЬНО создайте тестовую БД для разработки:
sudo scripts/create_test_db.sh
```

6. Запустите бота:
```bash
python main.py
```

## 🔧 Управление проектом

### Разработка:
```bash
# 🧪 ВАЖНО: Сначала создайте тестовую БД
sudo scripts/create_test_db.sh

# Запуск всех тестов (используют тестовую БД)
./scripts/run_tests.sh

# Integration тесты (используют тестовую БД)
./scripts/run_integration_tests.sh

# Manual диалоговые тесты
python tests/manual/dialogue_studies/ai_thinking_analysis.py

# Flow тесты бронирования (с тестовой БД)
python tests/manual/booking_flow_with_testdb.py
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

## �� Структура файлов

### Корень проекта (только важные файлы):
- `main.py` - точка входа приложения
- `agent.md` - инструкции для AI агента
- `README.md` - документация проекта
- `LICENSE` - лицензия
- `version.txt` - версия проекта
- `prompts.json` - AI промпты
- `requirements.txt` - зависимости Python
- `init_db.sql` - схема базы данных
- `.env` - переменные окружения
- `.gitignore` - исключения Git

### Организованные папки:
- `src/bot/` - модульная архитектура кода
- `tests/` - comprehensive testing framework
- `scripts/` - автоматизированные скрипты и утилиты
- `docs/` - документация и инструкции
- `logs/` - логи работы и отчеты
- `backup/` - старые версии файлов
- `messages/` - шаблоны сообщений
- `design/` - дизайн и макеты

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