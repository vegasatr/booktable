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

# Импорты из наших модулей
from src.bot.config import VERSION, TELEGRAM_TOKEN
from src.bot.database.users import save_user_to_db, get_user_preferences
from src.bot.managers.user_state import UserState
from src.bot.ai.core import ask
from src.bot.ai.translation import translate_message, detect_language

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
    try:
        query = update.callback_query
        lang = query.data.split('_')[1]
        logger.info(f"[LANGUAGE] Setting language to {lang}")
        context.user_data['language'] = lang
        context.user_data['awaiting_language'] = False
        await query.message.delete()
        
        user = update.effective_user
        client_number = save_user_to_db(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=lang
        )
        logger.info(f"User saved with client_number: {client_number}")
        
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
    """Показывает кнопки выбора бюджета"""
    keyboard = [
        [
            InlineKeyboardButton("$", callback_data="budget_1"),
            InlineKeyboardButton("$$", callback_data="budget_2"),
            InlineKeyboardButton("$$$", callback_data="budget_3"),
            InlineKeyboardButton("$$$$", callback_data="budget_4")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    state = UserState(context)
    message = await translate_message('budget_question', state.language)
    
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)

async def budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора бюджета"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    
    budget_number = query.data.split('_')[1]
    
    # Конвертируем числовое значение в символы доллара для базы данных
    budget_map = {
        '1': '$',
        '2': '$$',
        '3': '$$$',
        '4': '$$$$'
    }
    budget = budget_map.get(budget_number, budget_number)
    
    logger.info(f"[BUDGET_CALLBACK] Converting budget_number={budget_number} to budget={budget}")
    
    # Устанавливаем бюджет
    state = UserState(context)
    context._user_id = update.effective_user.id
    state.set_budget(budget)
    
    # Показываем сообщение о сохранении
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(0.5)
    budget_saved_msg = await translate_message('budget_saved', state.language)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=budget_saved_msg)
    
    # Показываем выбор локации
    await show_location_selection(update, context)
    
    # Обновляем команды меню после выбора бюджета
    await context.bot.set_my_commands([
        ("restart", "Перезапустить бота"),
        ("new_search", "Новый поиск")
    ])

async def show_location_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает выбор локации"""
    keyboard = [[
        InlineKeyboardButton("РЯДОМ", callback_data='location_near'),
        InlineKeyboardButton("РАЙОН", callback_data='location_area'),
        InlineKeyboardButton("ВЕЗДЕ", callback_data='location_any')
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "Подберу для Вас отличный ресторан! Поискать поблизости, в другом районе или в любом месте на Пхукете?"
    
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)

async def location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора локации"""
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    
    language = context.user_data.get('language', 'ru')
    
    if query.data == 'location_any':
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        context.user_data['location'] = 'any'
        msg = await translate_message('location_any_confirmed', language)
        await query.message.reply_text(msg)
        
        # Начинаем диалог с AI
        q = "Пользователь выбрал язык, бюджет и любое место на острове. Начни диалог." if language == 'ru' else "User selected language, budget and any location on the island. Start the conversation."
        try:
            a, chat_log = await ask(q, context.user_data['chat_log'], language)
            context.user_data['chat_log'] = chat_log
            await query.message.reply_text(a)
        except Exception as e:
            logger.error(f"Error in ask: {e}")
            error_message = await translate_message('error', language)
            await query.message.reply_text(error_message)
    else:
        # TODO: Реализовать другие варианты локации
        await query.message.reply_text("Эта функция будет доступна в следующем обновлении.")

async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Основной обработчик текстовых сообщений"""
    user = update.effective_user
    text = update.message.text.strip()
    
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
        client_number = save_user_to_db(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=detected_lang
        )
        logger.info(f"User saved with client_number: {client_number}")
        
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        welcome_message = await translate_message('welcome', detected_lang)
        await update.message.reply_text(welcome_message)
        
        await show_budget_buttons(update, context)
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

def main():
    """Основная функция запуска бота"""
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Базовые команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("new_search", new_search))
    
    # Обработчики callback-запросов
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(budget_callback, pattern="^budget_"))
    app.add_handler(CallbackQueryHandler(location_callback, pattern="^location_"))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, talk))
    
    # Устанавливаем команды и меню после запуска
    app.post_init = set_bot_commands
    
    # Запуск бота
    app.run_polling()

if __name__ == '__main__':
    main() 