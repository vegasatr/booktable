# Модуль Бронирования BookTable Bot

## Обзор

Модуль бронирования реализует полный цикл резервирования столиков в ресторанах согласно ТЗ. Модуль поддерживает два способа начала бронирования:

1. **По кнопке РЕЗЕРВ** - из интерфейса выбора ресторанов
2. **Из сообщения в чате** - распознавание намерения бронирования в тексте

## Архитектура

### Основные компоненты

```
src/bot/managers/booking_manager.py       # Основная логика бронирования
src/bot/handlers/booking_handlers.py     # Обработчики callback'ов  
src/bot/database/bookings.py             # Работа с базой данных
```

### Структура данных

**Таблица `bookings`:**
- `booking_number` - уникальный номер бронирования
- `date` - дата бронирования 
- `time` - время бронирования
- `client_name` - имя клиента
- `phone` - телефон клиента
- `guests` - количество гостей
- `restaurant` - название ресторана
- `booking_method` - способ бронирования (telegram/whatsapp)
- `restaurant_contact` - контакт ресторана для уведомлений
- `preferences` - особые пожелания клиента
- `client_code` - ID пользователя в мессенджере
- `status` - статус бронирования (pending/confirmed/cancelled)

## Процесс Бронирования

### 1. Инициация

**Сценарий A: Кнопка РЕЗЕРВ**
- Один ресторан → сразу к выбору времени
- Несколько ресторанов → выбор ресторана

**Сценарий B: Сообщение в чате**
- AI анализирует текст и ищет намерение бронирования
- Пытается определить ресторан из контекста
- При неудаче → запрос уточнения

### 2. Шаги Бронирования

1. **Выбор ресторана** (если несколько)
2. **Выбор времени**
   - 4 предустановленных слота (от текущего времени +15 мин)
   - Кнопка "ДРУГОЕ" для кастомного времени
3. **Количество гостей** (1-5)
4. **Дата**
   - СЕГОДНЯ / ЗАВТРА / ДРУГОЕ
   - Кастомная дата через AI парсинг
5. **Завершение и уведомления**

### 3. Обработка Кастомных Вводов

Система использует AI для парсинга:
- Времени: "половина восьмого вечера" → "19:30"
- Даты: "следующая пятница" → "DD.MM.YYYY"

## API Методы

### BookingManager

```python
# Начало бронирования по кнопке
await BookingManager.start_booking_from_button(update, context)

# Начало бронирования из чата
await BookingManager.start_booking_from_chat(update, context, message_text)

# Внутренние методы
await BookingManager._ask_for_time(update, context, restaurant)
await BookingManager._ask_for_guests(update, context)
await BookingManager._ask_for_date(update, context)
await BookingManager._complete_booking(update, context)
```

### Database Functions

```python
# Сохранение бронирования
booking_number = await save_booking_to_db(
    restaurant_name="Restaurant Name",
    client_name="John Doe", 
    phone="+1234567890",
    date_booking=date(2024, 6, 15),
    time_booking=time(19, 30),
    guests=2,
    restaurant_contact="@restaurant",
    client_code=12345
)

# Получение бронирования
booking = await get_booking_by_number(123)

# Обновление пожеланий
success = await update_booking_preferences(123, "Window table please")

# Получение данных ресторана
restaurant_data = await get_restaurant_working_hours("Restaurant Name")
```

### Callback Handlers

```python
# Основные обработчики
await book_restaurant_callback(update, context)          # РЕЗЕРВ
await book_restaurant_select_callback(update, context)   # Выбор ресторана
await book_time_callback(update, context)               # Выбор времени
await book_guests_callback(update, context)             # Количество гостей  
await book_date_callback(update, context)               # Дата

# Обработчики текстового ввода
await handle_custom_time_input(update, context)         # Кастомное время
await handle_custom_date_input(update, context)         # Кастомная дата
await handle_booking_preferences(update, context)       # Доп. пожелания
```

## Callback Data Patterns

```
book_restaurant            # Начало бронирования
book_restaurant_0          # Выбор ресторана по индексу
book_time_18:30           # Выбор времени 
book_time_custom          # Кастомное время
book_guests_2             # 2 гостя
book_date_today           # Сегодня
book_date_tomorrow        # Завтра  
book_date_custom          # Кастомная дата
```

## Уведомления в Рестораны

При завершении бронирования система отправляет уведомление в ресторан:

```
Новое бронирование от BookTable
Номер брони: 123
Имя: John Doe
Дата: 15.06.2024
Время: 19:30
Гостей: 2
Мессенджер: Telegram
Контакт: @johndoe
Если будут особые пожелания, я напишу позже
```

Дополнительные пожелания отправляются отдельным сообщением.

## Сообщения Пользователю

**При завершении:**
1. Подтверждение бронирования
2. Инструкции по поддержке (/support, /new_search)

**После бронирования:**
- Пользователь может написать дополнительные пожелания
- Система автоматически привязывает их к бронированию

## Обработка Ошибок

- **Нет ресторанов в контексте** → запрос уточнения
- **Ошибка сохранения в БД** → сообщение об ошибке
- **Неверный формат времени/даты** → повторный запрос
- **Неизвестный ресторан в тексте** → выбор из списка

## Тестирование

Модуль покрыт comprehensive тестами:

- **Unit тесты**: `tests/unit/test_booking_manager.py`, `tests/unit/test_database_bookings.py`
- **Integration тесты**: `tests/integration/test_booking_integration.py`

### Запуск тестов

```bash
# Все тесты бронирования
python -m pytest tests/unit/test_booking_manager.py tests/unit/test_database_bookings.py tests/integration/test_booking_integration.py -v

# Конкретный тест
python -m pytest tests/unit/test_booking_manager.py::TestBookingManager::test_start_booking_single_restaurant -v
```

## Интеграция с Main.py

Обработчики зарегистрированы в `main.py`:

```python
app.add_handler(CallbackQueryHandler(book_restaurant_callback, pattern="^book_restaurant$"))
app.add_handler(CallbackQueryHandler(book_restaurant_select_callback, pattern="^book_restaurant_\\d+$"))
app.add_handler(CallbackQueryHandler(book_time_callback, pattern="^book_time_"))
app.add_handler(CallbackQueryHandler(book_guests_callback, pattern="^book_guests_\\d+$"))
app.add_handler(CallbackQueryHandler(book_date_callback, pattern="^book_date_"))
```

Текстовые обработчики интегрированы в функцию `talk()`.

## Конфигурация Сообщений

Все сообщения определены в `messages/base_messages.txt`:

```json
{
    "booking_which_restaurant": "Which restaurant shall we book a table at?",
    "booking_time_question": "What time should I book the table for?",
    "booking_guests_question": "For how many guests?",
    "booking_date_question": "Are we booking for today, is that correct?",
    "booking_confirmation": "Thank you, your table has been booked!",
    "booking_instructions": "If you need help with this reservation..."
}
```

## Многоязычность

Модуль полностью поддерживает многоязычность через систему translate_message().

## Будущие Улучшения

- [ ] Отправка уведомлений в WhatsApp
- [ ] Парсинг working_hours из JSONB формата
- [ ] Отмена и изменение бронирований
- [ ] Напоминания о бронированиях
- [ ] Интеграция с внешними системами ресторанов 