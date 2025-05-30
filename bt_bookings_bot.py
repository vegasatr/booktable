#!/usr/bin/env python3
"""
BookTable Bookings Bot - Бот для менеджеров ресторанов
Получает уведомления о новых бронированиях
"""

import logging
import asyncio
import uuid
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.constants import ChatAction
from src.bot.database.connection import get_db_connection
from src.bot.ai.translation import translate_message, detect_language, translate_text
from psycopg2.extras import DictCursor

# API токен для бота менеджеров
BOOKINGS_BOT_TOKEN = "7753935644:AAH9CNbhe1sptlJj8VFtg7aQRSKnRNswqf8"

# Загружаем сообщения для бота менеджеров
with open('messages/bookings_bot_messages.txt', 'r', encoding='utf-8') as f:
    BOOKINGS_MESSAGES = json.load(f)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/bookings_bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting BookTable Bookings Bot for restaurant managers")

async def translate_bookings_message(message_key, language, **kwargs):
    """Переводит сообщения бота менеджеров"""
    try:
        base = BOOKINGS_MESSAGES.get(message_key, '')
        if not base:
            logger.error(f"[BOOKINGS_TRANSLATE] Message not found: {message_key}")
            return message_key
            
        # Подставляем параметры
        if kwargs:
            try:
                base = base.format(**kwargs)
            except KeyError as e:
                logger.error(f"[BOOKINGS_TRANSLATE] Format error: {e}")
        
        # Если английский - возвращаем как есть
        if language == 'en':
            return base
        
        # Переводим через AI
        translated = await translate_text(base, language)
        logger.info(f"[BOOKINGS_TRANSLATE] Translated to {language}: {translated}")
        return translated
        
    except Exception as e:
        logger.error(f"[BOOKINGS_TRANSLATE] Error: {e}")
        return BOOKINGS_MESSAGES.get(message_key, message_key)

async def translate_booking_status(status, language):
    """Переводит статус бронирования единообразно"""
    status_translations = {
        'pending': {
            'ru': 'ожидает подтверждения',
            'en': 'pending confirmation',
            'fr': 'en attente de confirmation',
            'ar': 'في انتظار التأكيد',
            'zh': '等待确认',
            'th': 'รอการยืนยัน'
        },
        'confirmed': {
            'ru': 'подтверждено',
            'en': 'confirmed',
            'fr': 'confirmé',
            'ar': 'مؤكد',
            'zh': '已确认',
            'th': 'ยืนยันแล้ว'
        },
        'cancelled': {
            'ru': 'отменено',
            'en': 'cancelled',
            'fr': 'annulé',
            'ar': 'ملغى',
            'zh': '已取消',
            'th': 'ยกเลิกแล้ว'
        }
    }
    
    # Если есть прямой перевод - используем его
    if status.lower() in status_translations and language in status_translations[status.lower()]:
        return status_translations[status.lower()][language]
    
    # Иначе AI перевод
    return await translate_text(status, language)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start - выбор языка и авторизация"""
    user = update.effective_user
    user_id = user.id
    username = user.username
    
    logger.info(f"[BOOKINGS_BOT] Start command from user {user_id} (@{username})")
    
    # Очищаем состояние пользователя
    context.user_data.clear()
    
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
    
    # Эффект набора текста
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    
    # Стартовое сообщение (всегда на английском + русском для понимания)
    welcome_text = BOOKINGS_MESSAGES["welcome_choose_language"]
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    context.user_data['awaiting_language'] = True
    context.user_data['user_id'] = user_id
    context.user_data['username'] = username

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора языка"""
    query = update.callback_query
    await query.answer()
    
    try:
        lang = query.data.split('_')[1]
        logger.info(f"[BOOKINGS_BOT] Language selected: {lang}")
        
        context.user_data['language'] = lang
        context.user_data['awaiting_language'] = False
        
        # Удаляем сообщение с выбором языка
        await query.message.delete()
        
        # Проверяем авторизацию менеджера
        user_id = context.user_data['user_id']
        username = context.user_data['username']
        
        authorized = await check_manager_authorization(user_id, username)
        
        if authorized:
            restaurants = authorized  # Список ресторанов менеджера
            
            # Сохраняем авторизованного менеджера
            context.user_data['authorized'] = True
            context.user_data['restaurants'] = restaurants
            
            # Формируем список ресторанов для сообщения
            restaurant_list = '\n'.join([f"🍽️ {r['name']}" for r in restaurants])
            
            # Переводим приветственное сообщение БЕЗ списка ресторанов
            welcome_base = await translate_bookings_message('welcome_authorized', lang)
            
            # Вставляем список ресторанов в переведенное сообщение
            welcome_message = welcome_base.format(restaurants=restaurant_list)
            
            # Кнопка для показа заказов
            button_text = await translate_bookings_message('button_show_orders', lang)
            keyboard = [[InlineKeyboardButton(button_text, callback_data="show_recent_bookings")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=user_id, 
                text=welcome_message, 
                reply_markup=reply_markup
            )
            
            # Логируем успешную авторизацию
            restaurant_names = [r['name'] for r in restaurants]
            logger.info(f"[BOOKINGS_BOT] Manager {username} ({user_id}) authorized for restaurants: {restaurant_names}")
            
        else:
            # Неавторизованный пользователь
            error_message = await translate_bookings_message(
                'access_denied', 
                lang, 
                username=username or 'username'
            )
            
            await context.bot.send_message(chat_id=user_id, text=error_message)
            logger.warning(f"[BOOKINGS_BOT] Unauthorized access attempt from {username} ({user_id})")
            
    except Exception as e:
        logger.error(f"[BOOKINGS_BOT] Error in language_callback: {e}")
        error_msg = await translate_bookings_message('error_occurred', context.user_data.get('language', 'en'))
        await query.message.reply_text(error_msg)

async def check_manager_authorization(user_id, username):
    """Проверяет авторизацию менеджера по базе данных"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Ищем рестораны где этот пользователь указан как контакт
        contact_patterns = []
        params = []
        
        if username:
            contact_patterns.append("booking_contact = %s")
            params.append(f"@{username}")
        
        # Также проверяем по user_id (если он указан как chat_id)
        contact_patterns.append("booking_contact = %s")
        params.append(str(user_id))
        
        if not contact_patterns:
            return False
        
        query = f"""
            SELECT name, booking_contact, location
            FROM restaurants 
            WHERE active = 'TRUE' AND ({' OR '.join(contact_patterns)})
            ORDER BY name
        """
        
        logger.info(f"[BOOKINGS_BOT] Authorization query: {query} with params: {params}")
        cur.execute(query, params)
        restaurants = cur.fetchall()
        
        cur.close()
        conn.close()
        
        if restaurants:
            return [dict(r) for r in restaurants]
        else:
            return False
            
    except Exception as e:
        logger.error(f"[BOOKINGS_BOT] Error checking authorization: {e}")
        return False

async def show_recent_bookings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает последние бронирования для ресторанов менеджера"""
    query = update.callback_query
    await query.answer()
    
    if not context.user_data.get('authorized'):
        error_msg = await translate_bookings_message('not_authorized', context.user_data.get('language', 'en'))
        await query.edit_message_text(error_msg)
        return
    
    language = context.user_data.get('language', 'en')
    restaurants = context.user_data.get('restaurants', [])
    restaurant_names = [r['name'] for r in restaurants]
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Получаем последние 10 бронирований для ресторанов менеджера
        cur.execute("""
            SELECT booking_number, restaurant, client_name, date, time, guests, status, preferences
            FROM bookings 
            WHERE restaurant = ANY(%s)
            ORDER BY booking_number DESC
            LIMIT 10
        """, (restaurant_names,))
        
        bookings = cur.fetchall()
        
        if bookings:
            # Переводим заголовок
            message = await translate_bookings_message('recent_bookings_title', language)
            message += "\n\n"
            
            for booking in bookings:
                prefs = booking['preferences'] or ""
                
                # Переводим статус
                status_translated = await translate_booking_status(booking['status'], language)
                
                # Переводим только шаблоны без конкретных данных
                if prefs:
                    prefs_translated = await translate_text(prefs, language)
                    # Переводим шаблон без подстановки данных
                    booking_template = await translate_bookings_message('booking_item_with_prefs', language)
                    booking_text = booking_template.format(
                        booking_number=booking['booking_number'],
                        restaurant=booking['restaurant'],  # Не переводим название ресторана
                        client_name=booking['client_name'],
                        date=booking['date'].strftime('%d.%m.%Y'),
                        time=booking['time'].strftime('%H:%M'),
                        guests=booking['guests'],
                        status=status_translated,
                        preferences=prefs_translated
                    )
                else:
                    # Переводим шаблон без подстановки данных
                    booking_template = await translate_bookings_message('booking_item', language)
                    booking_text = booking_template.format(
                        booking_number=booking['booking_number'],
                        restaurant=booking['restaurant'],  # Не переводим название ресторана
                        client_name=booking['client_name'],
                        date=booking['date'].strftime('%d.%m.%Y'),
                        time=booking['time'].strftime('%H:%M'),
                        guests=booking['guests'],
                        status=status_translated
                    )
                
                message += booking_text + "\n\n"
        else:
            message = await translate_bookings_message('no_bookings', language)
        
        # Без кнопок - просто текст
        await query.edit_message_text(message)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"[BOOKINGS_BOT] Error showing recent bookings: {e}")
        error_msg = await translate_bookings_message('error_occurred', language)
        await query.edit_message_text(error_msg)

async def show_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню (не используется, но оставляем для совместимости)"""
    query = update.callback_query
    await query.answer()
    
    if not context.user_data.get('authorized'):
        error_msg = await translate_bookings_message('not_authorized', context.user_data.get('language', 'en'))
        await query.edit_message_text(error_msg)
        return
    
    language = context.user_data.get('language', 'en')
    
    # Показываем основную кнопку
    button_text = await translate_bookings_message('button_show_orders', language)
    keyboard = [[InlineKeyboardButton(button_text, callback_data="show_recent_bookings")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    action_text = await translate_bookings_message('choose_action', language)
    await query.edit_message_text(action_text, reply_markup=reply_markup)

async def restart_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перезапуск бота"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем сообщение
    await query.message.delete()
    
    # Очищаем данные и запускаем заново
    context.user_data.clear()
    
    # Создаем фиктивное update для функции start
    fake_update = Update(
        update_id=query.message.message_id,
        message=query.message
    )
    
    await start(fake_update, context)

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /restart - перезапуск бота"""
    context.user_data.clear()
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений"""
    if context.user_data.get('awaiting_language'):
        # Определяем язык автоматически если пользователь написал вместо выбора кнопки
        try:
            text = update.message.text.strip()
            detected_lang = await detect_language(text)
            
            logger.info(f"[BOOKINGS_BOT] Detected language from text: {detected_lang}")
            
            # Устанавливаем язык
            context.user_data['language'] = detected_lang
            context.user_data['awaiting_language'] = False
            
            # Продолжаем авторизацию
            user_id = context.user_data['user_id']
            username = context.user_data['username']
            
            authorized = await check_manager_authorization(user_id, username)
            
            if authorized:
                restaurants = authorized
                context.user_data['authorized'] = True
                context.user_data['restaurants'] = restaurants
                
                # Формируем список ресторанов
                restaurant_list = '\n'.join([f"🍽️ {r['name']}" for r in restaurants])
                
                # Переводим приветственное сообщение БЕЗ списка ресторанов
                welcome_base = await translate_bookings_message('welcome_authorized', detected_lang)
                
                # Вставляем список ресторанов в переведенное сообщение
                welcome_message = welcome_base.format(restaurants=restaurant_list)
                
                # Кнопка для показа заказов
                button_text = await translate_bookings_message('button_show_orders', detected_lang)
                keyboard = [[InlineKeyboardButton(button_text, callback_data="show_recent_bookings")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(welcome_message, reply_markup=reply_markup)
            else:
                error_message = await translate_bookings_message(
                    'access_denied', 
                    detected_lang, 
                    username=username or 'username'
                )
                await update.message.reply_text(error_message)
                
        except Exception as e:
            logger.error(f"[BOOKINGS_BOT] Error in message handler: {e}")
            error_msg = await translate_bookings_message('error_occurred', 'en')
            await update.message.reply_text(error_msg)
        return
    
    if not context.user_data.get('authorized'):
        lang = context.user_data.get('language', 'en')
        error_msg = await translate_bookings_message('please_start', lang)
        await update.message.reply_text(error_msg)
        return
    
    # Показываем меню для авторизованных пользователей
    language = context.user_data.get('language', 'en')
    
    action_text = await translate_bookings_message('choose_action', language)
    button_text = await translate_bookings_message('button_show_orders', language)
    
    keyboard = [[InlineKeyboardButton(button_text, callback_data="show_recent_bookings")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(action_text, reply_markup=reply_markup)

async def send_booking_notification(booking_number, booking_data, restaurant_name, user_data):
    """
    Отправляет уведомление о новом бронировании всем менеджерам ресторана
    Эта функция будет вызываться из основного бота
    """
    try:
        # Получаем всех менеджеров для этого ресторана
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        cur.execute("""
            SELECT booking_contact
            FROM restaurants 
            WHERE name = %s AND active = 'TRUE'
        """, (restaurant_name,))
        
        result = cur.fetchone()
        if not result or not result['booking_contact']:
            logger.warning(f"[BOOKINGS_BOT] No booking contact for restaurant {restaurant_name}")
            return False
        
        booking_contact = result['booking_contact']
        
        # Формируем имя клиента
        client_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
        if not client_name:
            client_name = user_data.get('username', f"User_{user_data.get('id', 'Unknown')}")
        
        # Формируем уведомление (на английском, будет переведено при получении)
        message = BOOKINGS_MESSAGES["new_booking_notification"].format(
            booking_number=booking_number,
            restaurant=restaurant_name,
            client_name=client_name,
            date=booking_data['date'].strftime('%d.%m.%Y'),
            time=booking_data['time'].strftime('%H:%M'),
            guests=booking_data['guests'],
            username=user_data.get('username', user_data.get('id', 'Unknown'))
        )
        
        logger.info(f"[BOOKINGS_BOT] Booking notification prepared for {restaurant_name}: {message}")
        return True
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"[BOOKINGS_BOT] Error sending booking notification: {e}")
        return False

async def set_bot_commands(app):
    """Устанавливает команды бота в меню"""
    commands = [
        ("restart", "Restart the bot")
    ]
    
    await app.bot.set_my_commands(commands)
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

def main():
    """Основная функция запуска бота менеджеров"""
    app = ApplicationBuilder().token(BOOKINGS_BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(show_recent_bookings_callback, pattern="^show_recent_bookings$"))
    app.add_handler(CallbackQueryHandler(show_menu_callback, pattern="^show_menu$"))
    app.add_handler(CallbackQueryHandler(restart_bot_callback, pattern="^restart_bot$"))
    
    # Обработчик сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Устанавливаем команды меню
    app.post_init = set_bot_commands
    
    # Запуск бота
    logger.info("[BOOKINGS_BOT] Starting BookTable Bookings Bot...")
    app.run_polling()

if __name__ == '__main__':
    main() 