#!/usr/bin/env python
"""
BookTable Bot - Модульная версия
"""

import logging
import uuid
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, MenuButtonCommands
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.constants import ChatAction
from src.bot.database.connection import get_db_connection
from psycopg2.extras import DictCursor

# Импорты из наших модулей
from src.bot.config import VERSION, TELEGRAM_TOKEN
from src.bot.database.users import save_user_to_db, get_user_preferences
from src.bot.managers.user_state import UserState
from src.bot.ai.core import ask, restaurant_chat, detect_area_from_text, general_chat, is_about_restaurants
from src.bot.ai.translation import translate_message, detect_language, translate_text
from src.bot.constants import PHUKET_AREAS
from src.bot.utils.geo import get_nearest_area
from src.bot.managers.restaurant_display import show_restaurants
from src.bot.handlers.booking_handlers import (
    book_restaurant_callback, book_restaurant_select_callback,
    book_time_callback, book_guests_callback, book_date_callback,
    handle_custom_time_input, handle_custom_date_input, handle_booking_preferences
)
from src.bot.managers.booking_manager import BookingManager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.info(f"Starting BookTable bot version {VERSION}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Эффект набора текста перед приветствием
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    
    # Первое приветственное сообщение
    await update.message.reply_text(
        f'Hello and welcome to BookTable.AI v{VERSION}!\n'
        'I will help you find the perfect restaurant in Phuket and book a table in seconds.'
    )

    # Кнопки выбора языка
    keyboard = [
        [
            InlineKeyboardButton("Русский", callback_data="lang_ru"),
            InlineKeyboardButton("English", callback_data="lang_en")
        ],
        [
            InlineKeyboardButton("Français", callback_data="lang_fr"),
            InlineKeyboardButton("العربية", callback_data="lang_ar")
        ],
        [
            InlineKeyboardButton("中文", callback_data="lang_zh"),
            InlineKeyboardButton("ภาษาไทย", callback_data="lang_th")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Эффект набора текста перед выбором языка
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    
    # Отправляем объединенное сообщение с кнопками
    await update.message.reply_text(
        'Please choose your language or just type a message — I understand more than 120 languages and will reply in yours!',
        reply_markup=reply_markup
    )

    context.user_data['awaiting_language'] = True
    context.user_data['chat_log'] = []
    context.user_data['sessionid'] = str(uuid.uuid4())
    logger.info("New session with %s", user.username)

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора языка"""
    query = update.callback_query
    try:
        lang = query.data.split('_')[1]
        logger.info(f"[LANGUAGE] Setting language to {lang}")
        context.user_data['language'] = lang
        context.user_data['awaiting_language'] = False
        await query.message.delete()
        
        user = update.effective_user
        save_user_to_db(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=lang
        )
        logger.info(f"User saved to database")
        
        await context.bot.send_chat_action(chat_id=update.effective_user.id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        welcome_message = await translate_message('welcome', lang)
        if query.message:
            welcome_msg = await query.message.reply_text(welcome_message)
        else:
            welcome_msg = await context.bot.send_message(chat_id=update.effective_user.id, text=welcome_message)
        
        # Сохраняем ID приветственного сообщения для последующего удаления
        context.user_data['welcome_message_id'] = welcome_msg.message_id
        
        await show_budget_buttons(update, context)
    except Exception as e:
        logger.error(f"Error in language_callback: {e}")
        try:
            if hasattr(query, 'message') and query.message:
                await query.message.reply_text("Произошла ошибка. Пожалуйста, попробуйте ещё раз.")
            else:
                await context.bot.send_message(chat_id=update.effective_user.id, text="Произошла ошибка. Пожалуйста, попробуйте ещё раз.")
        except Exception as send_e:
            logger.error(f"Failed to send error message: {send_e}")

async def show_budget_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает кнопки выбора бюджета - использует BudgetManager"""
    from src.bot.managers.budget_manager import BudgetManager
    await BudgetManager.show_budget_selection(update, context)

async def budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора бюджета - использует BudgetManager"""
    budget_number = update.callback_query.data.split('_')[1]
    
    # Конвертируем числовое значение в символы доллара для базы данных
    budget_map = {
        '1': '$',
        '2': '$$',
        '3': '$$$',
        '4': '$$$$'
    }
    budget = budget_map.get(budget_number, budget_number)
    
    logger.info(f"[BUDGET_CALLBACK] Converting budget_number={budget_number} to budget={budget}")
    
    from src.bot.managers.budget_manager import BudgetManager
    await BudgetManager.handle_budget_change(update, context, budget)
    
    # Обновляем команды меню после выбора бюджета
    await context.bot.set_my_commands([
        ("restart", "Перезапустить бота"),
        ("new_search", "Новый поиск"),
        ("filter", "Проверить текущий бюджет")
    ])

async def show_location_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает выбор локации - использует LocationManager"""
    from src.bot.managers.location_manager import LocationManager
    await LocationManager.show_location_selection(update, context)

async def location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора локации"""
    query = update.callback_query
    await query.answer()
    
    language = context.user_data.get('language', 'ru')
    chat_id = query.message.chat_id
    
    await query.message.delete()
    
    if query.data == 'location_near':
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        keyboard = [[KeyboardButton("📍 Мое местоположение", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        msg = await translate_message('location_send', language)
        await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup)
        context.user_data['awaiting_location_or_area'] = True
        return
    elif query.data == 'location_area':
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        areas = list(PHUKET_AREAS.items())
        keyboard = []
        for i in range(0, len(areas), 2):
            row = []
            row.append(InlineKeyboardButton(areas[i][1], callback_data=f'area_{areas[i][0]}'))
            if i + 1 < len(areas):
                row.append(InlineKeyboardButton(areas[i+1][1], callback_data=f'area_{areas[i+1][0]}'))
            keyboard.append(row)
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = await translate_message('choose_area_instruction', language)
        await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup)
        context.user_data['awaiting_location_or_area'] = True
    elif query.data == 'location_any':
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        context.user_data['location'] = 'any'
        msg = await translate_message('location_any_confirmed', language)
        await context.bot.send_message(chat_id=chat_id, text=msg)
        
        # Начинаем диалог с AI
        q = "Пользователь выбрал язык, бюджет и любое место на острове. Начни диалог." if language == 'ru' else "User selected language, budget and any location on the island. Start the conversation."
        try:
            chat_log = context.user_data.get('chat_log', [])
            a, chat_log = await ask(q, chat_log, language)
            context.user_data['chat_log'] = chat_log
            await context.bot.send_message(chat_id=chat_id, text=a)
        except Exception as e:
            logger.error(f"Error in ask: {e}")
            error_message = await translate_message('error', language)
            await context.bot.send_message(chat_id=chat_id, text=error_message)

async def area_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора района"""
    query = update.callback_query
    await query.answer()
    
    language = context.user_data.get('language', 'ru')
    area_id = query.data[len('area_'):]
    chat_id = query.message.chat_id
    
    await query.message.delete()
    
    if area_id == 'other':
        other_message = await translate_message('other_area_prompt', language)
        await context.bot.send_message(chat_id=chat_id, text=other_message)
        context.user_data['awaiting_area_input'] = True
        return
    
    area_name = PHUKET_AREAS[area_id]
    context.user_data['location'] = {'area': area_id, 'name': area_name}
    
    # Показываем рестораны
    await show_restaurants(update, context)

async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик текстовых сообщений"""
    user = update.effective_user
    text = update.message.text.strip()
    language = context.user_data.get('language', 'en')
    
    logger.info(f"[TALK] User {user.id} sent message: {text}")
    
    # Проверяем на ввод кастомного времени/даты для бронирования
    if await handle_custom_time_input(update, context):
        return
    if await handle_custom_date_input(update, context):
        return
    if await handle_booking_preferences(update, context):
        return
    
    # Проверяем на намерение бронирования в сообщении
    booking_intent = await _detect_booking_intent(text, language)
    if booking_intent:
        await BookingManager.start_booking_from_chat(update, context, text)
        return

    # Проверяем состояние пользователя
    state = UserState(context)
    
    # Если пользователь еще не выбрал бюджет, игнорируем сообщение
    if not state.budget:
        logger.info(f"[TALK] User {user.username} sent message without budget selected, ignoring")
        return

    detected_lang = await detect_language(text)
    language = context.user_data.get('language', detected_lang)
    
    logger.info("Processing message from %s: %s", user.username, text)
    
    # Если это первое сообщение после старта
    if context.user_data.get('awaiting_language'):
        context.user_data['awaiting_language'] = False
        save_user_to_db(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=detected_lang
        )
        logger.info(f"User saved to database")
        
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        welcome_message = await translate_message('welcome', detected_lang)
        await update.message.reply_text(welcome_message)
        
        await show_budget_buttons(update, context)
        return
                        
    # Если ожидаем вопрос о ресторане
    if context.user_data.get('awaiting_restaurant_question'):
        context.user_data['awaiting_restaurant_question'] = False
        
        # Обрабатываем вопрос о ресторане через AI
        restaurant_info = context.user_data.get('restaurant_info', '')
        
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        try:
            # Используем специализированную функцию для вопросов о ресторанах
            response = await restaurant_chat(text, restaurant_info, language, context)
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in restaurant_chat: {e}")
            error_msg = await translate_message('error', language)
            await update.message.reply_text(error_msg)
        return

    # Если ожидаем ввод района
    if context.user_data.get('awaiting_area_input'):
        context.user_data['awaiting_area_input'] = False
        
        # Определяем район из текста
        area_key = await detect_area_from_text(text, language)
        
        if area_key:
            area_name = PHUKET_AREAS.get(area_key, text)
            context.user_data['location'] = {'area': area_key, 'name': area_name}
            
            # Показываем рестораны
            await show_restaurants(update, context)
        else:
            # Если не удалось определить район, показываем кнопки выбора
            await show_location_selection(update, context)
        return
    
    # Отправляем в AI для обработки
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    
    try:
        response, chat_log = await ask(text, context.user_data.get('chat_log'), language)
        context.user_data['chat_log'] = chat_log
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error in talk: {e}")
        error_msg = await translate_message('error', language)
        await update.message.reply_text(error_msg)

# Простые команды
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перезапуск бота: сброс состояния и стартовое приветствие"""
    context.user_data.clear()
    await start(update, context)

async def new_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает новый поиск ресторана, сохраняя только бюджет"""
    logger.info("[NEW_SEARCH] Starting new search")
    user_id = update.effective_user.id
    
    # Получаем сохраненные предпочтения из базы
    preferences = get_user_preferences(user_id)
    
    # Сохраняем только бюджет
    if preferences and preferences.get('budget'):
        context.user_data['budget'] = preferences['budget']
    else:
        # Если бюджет не найден, предлагаем его выбрать
        await show_budget_buttons(update, context)
        return
    
    # Показываем выбор локации
    await show_location_selection(update, context)

async def set_bot_commands(app):
    """Устанавливает команды бота в меню"""
    commands = [
        ("restart", "Перезапустить бота"),
        ("new_search", "Новый поиск")
    ]
    
    await app.bot.set_my_commands(commands)
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик получения геолокации"""
    try:
        location = update.message.location
        language = context.user_data.get('language', 'ru')
        
        logger.info(f"[LOCATION] Received coordinates: {location.latitude}, {location.longitude}")
        
        # Сохраняем координаты в контексте
        context.user_data['location'] = {
            'coordinates': (location.latitude, location.longitude),
            'latitude': location.latitude,
            'longitude': location.longitude
        }
        
        try:
            # Пытаемся получить адрес (опционально, может не работать без геокодера)
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET coordinates = POINT(%s, %s), user_coords = %s WHERE telegram_user_id = %s",
                (location.longitude, location.latitude, f"{location.latitude},{location.longitude}", update.effective_user.id)
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving coordinates to database: {e}")
        
        # Определяем ближайший район
        nearest_area = get_nearest_area(location.latitude, location.longitude)
        
        if nearest_area:
            area_name = PHUKET_AREAS[nearest_area]
            context.user_data['location'] = {'area': nearest_area, 'name': area_name}
            
            # Показываем рестораны
            await show_restaurants(update, context)
        else:
            await update.message.reply_text("Не удалось определить район по координатам. Пожалуйста, выберите район вручную.")
            
    except Exception as e:
        logger.error(f"[LOCATION] Error handling location: {e}")
        await update.message.reply_text("Произошла ошибка при обработке локации. Попробуйте выбрать район вручную.")

async def ask_about_restaurant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки 'Вопрос о ресторане'"""
    query = update.callback_query
    await query.answer()
    
    language = context.user_data.get('language', 'ru')
    
    # Отправляем приглашение задать вопрос
    prompt_msg = await translate_message('ask_question_prompt', language)
    await query.message.reply_text(prompt_msg)
    
    # Устанавливаем флаг ожидания вопроса
    context.user_data['awaiting_restaurant_question'] = True

async def choose_area_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки выбора района"""
    query = update.callback_query
    await query.answer()
    # Удаляем сообщение с кнопками
    await query.message.delete()
    # Показываем выбор района
    areas = list(PHUKET_AREAS.items())
    keyboard = []
    for i in range(0, len(areas), 2):
        row = []
        row.append(InlineKeyboardButton(areas[i][1], callback_data=f'area_{areas[i][0]}'))
        if i + 1 < len(areas):
            row.append(InlineKeyboardButton(areas[i+1][1], callback_data=f'area_{areas[i+1][0]}'))
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)
    language = context.user_data.get('language', 'ru')
    msg = await translate_message('choose_area_instruction', language)
    await query.message.reply_text(msg, reply_markup=reply_markup)

async def show_other_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки показа ресторанов в других ценовых категориях"""
    query = update.callback_query
    await query.answer()
    # Удаляем сообщение с кнопками
    try:
        await query.message.delete()
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения с кнопками: {e}")
    
    location = context.user_data.get('location')
    budget = context.user_data.get('budget')
    language = context.user_data.get('language', 'ru')
    
    if not isinstance(location, dict) or 'area' not in location:
        await update.effective_chat.send_message("Ошибка: не удалось определить район для поиска ресторанов.")
        return
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        area_key = location['area']
        from src.bot.constants import AREA_DB_MAPPING
        db_area_name = AREA_DB_MAPPING.get(area_key, location.get('name', ''))
        
        cur.execute(
            """
            SELECT name, average_check, location FROM restaurants
            WHERE LOWER(location) ILIKE %s
            AND average_check::text != %s AND active ILIKE 'true'
            ORDER BY name
            """,
            (f"%{db_area_name.lower()}%", budget)
        )
        rows = cur.fetchall()
        
        if not rows:
            await update.effective_chat.send_message("В этом районе нет ресторанов в других ценовых категориях. Попробуйте выбрать другой район.")
            return
        
        # Получаем подробную информацию о ресторанах
        names = tuple([r['name'] for r in rows])
        cur.execute(
            """
            SELECT name, average_check, cuisine, features, atmosphere, story_or_concept
            FROM restaurants
            WHERE name IN %s
            """,
            (names,)
        )
        details = {r['name']: r for r in cur.fetchall()}
        
        msg = "Рестораны в этом районе с другим средним чеком:\n\n"
        for r in rows:
            d = details.get(r['name'], {})
            cuisine = d.get('cuisine') or ''
            features = d.get('features')
            if isinstance(features, list):
                features = ', '.join(features)
            elif features is None:
                features = ''
            
            # Переводим cuisine и описание
            if language != 'en':
                try:
                    if cuisine:
                        from src.bot.managers.restaurant_display import translate_cuisine
                        cuisine = await translate_cuisine(cuisine, language)
                    if features:
                        features = await translate_text(features, language)
                except Exception as e:
                    logger.error(f"Ошибка перевода описания ресторана: {e}")
            
            msg += f"• {r['name']} — {r['average_check']}\n"
            if cuisine:
                msg += f"{cuisine}\n"
            if features:
                msg += f"{features}\n"
            msg += "\n"
        
        await update.effective_chat.send_message(msg)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Ошибка в show_other_price_callback: {e}")
        await update.effective_chat.send_message(f"Ошибка поиска ресторанов: {e}")

async def book_restaurant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки бронирования ресторана - теперь использует BookingManager"""
    from src.bot.handlers.booking_handlers import book_restaurant_callback as new_handler
    await new_handler(update, context)

async def change_budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки изменения бюджета"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    
    # Сохраняем контекст возврата
    state = UserState(context)
    return_context = {
        'screen': 'restaurant_list',
        'budget': state.budget,
        'location': state.location,
        'language': state.language
    }
    
    # Показываем кнопки выбора бюджета с контекстом возврата
    from src.bot.managers.budget_manager import BudgetManager
    await BudgetManager.show_budget_selection(update, context, return_context)

async def check_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает текущий выбранный бюджет"""
    language = context.user_data.get('language', 'ru')
    budget = context.user_data.get('budget')
    
    if budget:
        message = await translate_message('current_budget', language, budget=budget)
    else:
        message = await translate_message('no_budget', language)
    
    await update.message.reply_text(message)

async def _detect_booking_intent(text, language):
    """Определяет намерение бронирования в сообщении пользователя"""
    try:
        # Ключевые слова для бронирования
        booking_keywords = {
            'en': ['book', 'reserve', 'reservation', 'table', 'booking'],
            'ru': ['забронировать', 'резерв', 'бронь', 'столик', 'бронирование']
        }
        
        text_lower = text.lower()
        keywords = booking_keywords.get(language, booking_keywords['en'])
        
        # Простая проверка по ключевым словам
        return any(keyword in text_lower for keyword in keywords)
        
    except Exception as e:
        logger.error(f"[BOOKING] Error detecting booking intent: {e}")
        return False

def main():
    """Основная функция запуска бота"""
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Базовые команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("new_search", new_search))
    app.add_handler(CommandHandler("filter", check_budget))
    
    # Обработчики callback-запросов
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(budget_callback, pattern="^budget_"))
    app.add_handler(CallbackQueryHandler(location_callback, pattern="^location_"))
    app.add_handler(CallbackQueryHandler(area_callback, pattern="^area_"))
    app.add_handler(CallbackQueryHandler(ask_about_restaurant_callback, pattern="^ask_about_restaurant$"))
    app.add_handler(CallbackQueryHandler(choose_area_callback, pattern="^choose_area$"))
    app.add_handler(CallbackQueryHandler(show_other_price_callback, pattern="^show_other_price$"))
    app.add_handler(CallbackQueryHandler(book_restaurant_callback, pattern="^book_restaurant$"))
    app.add_handler(CallbackQueryHandler(book_restaurant_select_callback, pattern="^book_restaurant_\\d+$"))
    app.add_handler(CallbackQueryHandler(book_time_callback, pattern="^book_time_"))
    app.add_handler(CallbackQueryHandler(book_guests_callback, pattern="^book_guests_\\d+$"))
    app.add_handler(CallbackQueryHandler(book_date_callback, pattern="^book_date_"))
    app.add_handler(CallbackQueryHandler(change_budget_callback, pattern="^change_budget$"))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, talk))
    
    # Устанавливаем команды и меню после запуска
    app.post_init = set_bot_commands
    
    # Запуск бота
    app.run_polling()

if __name__ == '__main__':
    main() 