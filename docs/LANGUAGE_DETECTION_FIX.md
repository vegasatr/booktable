# Исправление проблемы с переводом сообщений бронирования

## 🐛 Описание проблемы

Сообщения в диалоге бронирования переводились непоследовательно:
- Рекомендации ресторанов переводились корректно на русский
- Сообщения диалога бронирования оставались на английском: "What time should I book the table for?"

## 🔍 Анализ причины

Проблема была в логике определения языка в функции `talk()` в файле `main.py`:

```python
# БЫЛО (проблематично):
language = context.user_data.get('language', 'en')  # Строка 249 - en по умолчанию!
# ... далее по коду функции
detected_lang = await detect_language(text)  # Строка 275
language = context.user_data.get('language', detected_lang)  # Строка 276 - ПОЗДНО!
```

**Проблема:** Язык устанавливался как `'en'` в начале функции и использовался в функциях бронирования до правильного определения языка.

## 🔧 Исправление

### 1. Перенос определения языка в начало функции

```python
# СТАЛО (правильно):
async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text.strip()
    
    # Определяем язык в самом начале
    detected_lang = await detect_language(text)
    language = context.user_data.get('language', detected_lang)
    
    # Если язык не установлен в контексте, устанавливаем определенный
    if 'language' not in context.user_data:
        context.user_data['language'] = language
```

### 2. Исправление ссылок на переменные

```python
# Заменено detected_lang на language в блоке первого сообщения:
save_user_to_db(language=language)  # БЫЛО: language=detected_lang
welcome_message = await translate_message('welcome', language)  # БЫЛО: detected_lang
```

### 3. Добавлено логирование для отладки

```python
logger.info(f"[BOOKING] _ask_for_time: language={language}, user_data keys: {list(context.user_data.keys())}")
```

## 📊 Результат

### Было:
❌ Переводы работали непоследовательно  
❌ Сообщения бронирования оставались на английском  
❌ Дефолтный язык `'en'` перекрывал автоопределение  

### Стало:
✅ Язык определяется сразу в начале обработки сообщения  
✅ Все сообщения диалога бронирования переводятся корректно  
✅ Автоопределение языка работает надежно  
✅ Добавлено логирование для контроля

## 🚀 Deployment

Исправления применены в файлах:
- `main.py` - исправлена логика определения языка
- `src/bot/managers/booking_manager.py` - добавлено логирование

После перезапуска бота все сообщения бронирования должны корректно переводиться на язык пользователя. 