# Скрипты для работы с BookTable

## db_tool.py - Универсальный инструмент для работы с базой данных

Позволяет выполнять любые операции с базой данных через командную строку без написания отдельных скриптов.

### Основные возможности:
- ✅ **SELECT** - выборка данных
- ✅ **UPDATE** - обновление записей  
- ✅ **COUNT** - подсчёт записей
- ✅ **DESCRIBE** - структура таблицы
- ✅ **QUERY** - произвольный SQL

### Примеры использования:

#### 1. Просмотр данных
```bash
# Показать все рестораны с контактами
python3 scripts/db_tool.py --action select --table restaurants --fields "name,booking_contact"

# Последние 10 бронирований
python3 scripts/db_tool.py --action select --table bookings --fields "*" --order "booking_number DESC" --limit 10

# Пользователи по языку
python3 scripts/db_tool.py --action select --table users --where "language = 'ru'"
```

#### 2. Обновление данных
```bash
# Обновить контакт одного ресторана
python3 scripts/db_tool.py --action update --table restaurants --set "booking_contact='@newmanager'" --where "name='Nitan'"

# Обновить всех менеджеров
python3 scripts/db_tool.py --action update --table restaurants --set "booking_contact='@alextex'" --where "booking_contact IS NOT NULL"

# Изменить статус бронирования
python3 scripts/db_tool.py --action update --table bookings --set "status='confirmed'" --where "booking_number=5"
```

#### 3. Статистика
```bash
# Количество активных ресторанов
python3 scripts/db_tool.py --action count --table restaurants --where "active = 'TRUE'"

# Количество бронирований за сегодня
python3 scripts/db_tool.py --action count --table bookings --where "date = CURRENT_DATE"

# Количество пользователей по языкам
python3 scripts/db_tool.py --action query --sql "SELECT language, COUNT(*) as users FROM users GROUP BY language"
```

#### 4. Структура таблиц
```bash
# Посмотреть структуру таблицы ресторанов
python3 scripts/db_tool.py --action describe --table restaurants

# Структура таблицы бронирований
python3 scripts/db_tool.py --action describe --table bookings
```

#### 5. Сложные запросы
```bash
# Статистика бронирований по ресторанам
python3 scripts/db_tool.py --action query --sql "SELECT restaurant, COUNT(*) as bookings FROM bookings GROUP BY restaurant ORDER BY bookings DESC"

# Пользователи без телефона
python3 scripts/db_tool.py --action query --sql "SELECT client_name, telegram_user_id FROM users WHERE phone IS NULL"

# Бронирования на завтра
python3 scripts/db_tool.py --action query --sql "SELECT * FROM bookings WHERE date = CURRENT_DATE + INTERVAL '1 day'"
```

### Безопасность:
- ⚠️ **UPDATE без WHERE** требует подтверждения
- ✅ Автоматический **rollback** при ошибках
- ✅ Проверка обязательных параметров

### Требования:
- PostgreSQL должен быть запущен
- База данных `booktable` должна существовать  
- Пользователь `root` должен иметь доступ к базе

---

## check_db.py - Просмотр пользователей

Простой скрипт для быстрого просмотра всех пользователей в системе.

```bash
python3 scripts/check_db.py
``` 