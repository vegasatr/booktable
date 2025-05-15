#!/usr/bin/env python

import logging, os, uuid, json
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from dotenv import load_dotenv
from openai import OpenAI
import psycopg2
from psycopg2.extras import DictCursor

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Получаем токены из переменных окружения
telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
openai_api_key = os.getenv('OPENAI_API_KEY')

# Инициализация клиента OpenAI
client = OpenAI(api_key=openai_api_key)

# Подключение к базе данных
def get_db_connection():
    try:
        logger.info("Attempting to connect to database via socket")
        conn = psycopg2.connect(
            dbname="booktable",
            user="root",
            host="/var/run/postgresql"
        )
        logger.info("Successfully connected to database")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error: {str(e)}")
        logger.error(f"Error code: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'}")
        logger.error(f"Error message: {e.pgerror if hasattr(e, 'pgerror') else 'N/A'}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to database: {str(e)}")
        logger.exception("Full traceback:")
        raise

# Функция для сохранения пользователя в базу
def save_user_to_db(user_id, username, first_name, last_name, language):
    conn = None
    cur = None
    try:
        logger.info(f"Attempting to save user: id={user_id}, username={username}, first_name={first_name}, last_name={last_name}, language={language}")
        
        conn = get_db_connection()
        logger.info("Database connection established")
        
        cur = conn.cursor(cursor_factory=DictCursor)
        logger.info("Cursor created")
        
        # Формируем имя пользователя
        client_name = username or f"{first_name or ''} {last_name or ''}".strip() or str(user_id)
        logger.info(f"Formed client_name: {client_name}")
        
        # Проверяем, существует ли пользователь
        check_query = "SELECT client_number FROM users WHERE telegram_user_id = %s"
        logger.info(f"Executing query: {check_query} with params: {user_id}")
        cur.execute(check_query, (user_id,))
        existing_user = cur.fetchone()
        logger.info(f"Existing user check result: {existing_user}")
        
        if existing_user:
            # Обновляем существующего пользователя
            update_query = """
                UPDATE users 
                SET client_name = %s, language = %s 
                WHERE telegram_user_id = %s
                RETURNING client_number
            """
            logger.info(f"Executing update query with params: client_name={client_name}, language={language}, user_id={user_id}")
            cur.execute(update_query, (client_name, language, user_id))
            client_number = cur.fetchone()['client_number']
            logger.info(f"Updated existing user with client_number: {client_number}")
        else:
            # Создаем нового пользователя
            insert_query = """
                INSERT INTO users (telegram_user_id, client_name, language)
                VALUES (%s, %s, %s)
                RETURNING client_number
            """
            logger.info(f"Executing insert query with params: user_id={user_id}, client_name={client_name}, language={language}")
            cur.execute(insert_query, (user_id, client_name, language))
            client_number = cur.fetchone()['client_number']
            logger.info(f"Created new user with client_number: {client_number}")
        
        conn.commit()
        logger.info(f"Transaction committed successfully")
        return client_number
    except Exception as e:
        if conn:
            conn.rollback()
            logger.info("Transaction rolled back due to error")
        logger.error(f"Error saving user to database: {e}")
        logger.exception("Full traceback:")
        raise
    finally:
        if cur:
            cur.close()
            logger.info("Cursor closed")
        if conn:
            conn.close()
            logger.info("Database connection closed")

# Загружаем промпт
with open('prompt.txt', 'r', encoding='utf-8') as f:
    system_prompt = f.read().strip()

# Базовый контекст для ChatGPT
start_convo = [
    {"role": "system", "content": system_prompt}
]

def is_this_user_allowed(user_id):
    allowed_users = os.getenv('ALLOWED_USERS', '').split(',')
    return str(user_id) in allowed_users

def ask(q, chat_log=None):
    if chat_log is None:
        chat_log = start_convo.copy()
    chat_log = chat_log + [{"role": "user", "content": q}]
    response = client.chat.completions.create(
        model="gpt-4",
        messages=chat_log,
        temperature=0.7,
        max_tokens=1000
    )
    answer = response.choices[0].message.content
    chat_log = chat_log + [{"role": "assistant", "content": answer}]
    return answer, chat_log

def append_interaction_to_chat_log(q, a, chat_log=None):
    if chat_log is None:
        chat_log = start_convo.copy()
    chat_log = chat_log + [{"role": "user", "content": q}]
    chat_log = chat_log + [{"role": "assistant", "content": a}]
    return chat_log

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user["id"]
    username = user["username"]

    # Первое приветственное сообщение
    await update.message.reply_text(
        'Hello and welcome to BookTable.AI!\n'
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
    
    # Отправляем объединенное сообщение с кнопками
    await update.message.reply_text(
        'Please choose your language or just type a message — I understand more than 120 languages and will reply in yours!',
        reply_markup=reply_markup
    )

    context.user_data['awaiting_language'] = True
    context.user_data['chat_log'] = start_convo.copy()
    context.user_data['sessionid'] = str(uuid.uuid4())
    logger.info("New session with %s", username)

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        logger.info(f"Received callback query: {query.data}")
        
        # Получаем выбранный язык из callback_data
        lang = query.data.split('_')[1]
        logger.info(f"Selected language: {lang}")
        
        context.user_data['language'] = lang
        context.user_data['awaiting_language'] = False
        
        # Удаляем сообщение с кнопками выбора языка
        await query.message.delete()
        
        # Сохраняем пользователя в базу данных
        user = update.effective_user
        logger.info(f"Processing user: {user.id} ({user.username})")
        
        client_number = save_user_to_db(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=lang
        )
        
        logger.info(f"User saved with client_number: {client_number}")
        
        # Отправляем приветствие на выбранном языке
        welcome_messages = {
            'ru': "Я знаю о ресторанах на Пхукете всё.",
            'en': "I know everything about restaurants in Phuket.",
            'fr': "Je connais tout sur les restaurants de Phuket.",
            'ar': "أعرف كل شيء عن المطاعم في بوكيت.",
            'zh': "我了解普吉岛的所有餐厅。",
            'th': "ผมรู้ทุกอย่างเกี่ยวกับร้านอาหารในภูเก็ต"
        }
        
        welcome_message = welcome_messages.get(lang, welcome_messages['en'])
        logger.info(f"Sending welcome message: {welcome_message}")
        
        # Отправляем приветствие на выбранном языке
        await query.message.reply_text(welcome_message)
        
        # Показываем кнопки выбора бюджета
        keyboard = [
            [
                InlineKeyboardButton("$", callback_data="budget_1"),
                InlineKeyboardButton("$$", callback_data="budget_2"),
                InlineKeyboardButton("$$$", callback_data="budget_3"),
                InlineKeyboardButton("$$$$", callback_data="budget_4")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "С каким средним чеком подберем ресторан?" if lang == 'ru' else "What price range would you prefer for the restaurant?",
            reply_markup=reply_markup
        )
        
        # Инициализируем чат с ChatGPT
        q = "Пользователь выбрал язык. Начни диалог." if lang == 'ru' else "User selected language. Start the conversation."
        try:
            a, chat_log = ask(q, context.user_data['chat_log'])
            context.user_data['chat_log'] = chat_log
            logger.info("Chat initialized successfully")
        except Exception as e:
            logger.error(f"Error in ask: {e}")
            logger.exception("Full traceback:")
            
    except Exception as e:
        logger.error(f"Error in language_callback: {e}")
        logger.exception("Full traceback:")
        if query:
            await query.message.reply_text(
                "Произошла ошибка. Пожалуйста, попробуйте еще раз." if context.user_data.get('language') == 'ru'
                else "An error occurred. Please try again."
            )

async def show_budget_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("$", callback_data="budget_1"),
            InlineKeyboardButton("$$", callback_data="budget_2"),
            InlineKeyboardButton("$$$", callback_data="budget_3"),
            InlineKeyboardButton("$$$$", callback_data="budget_4")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "С каким средним чеком подберем ресторан?" if context.user_data.get('language') == 'ru' else "What price range would you prefer for the restaurant?",
        reply_markup=reply_markup
    )

async def budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer(text="", show_alert=False)
    
    # Обработка выбора бюджета
    budget = query.data.split('_')[1]
    
    # Сохраняем выбранный бюджет
    context.user_data['budget'] = budget
    
    # Показываем сообщение о сохранении
    message = "Запомнил ваш выбор. Его всегда можно изменить. Расскажите, что бы вам хотелось сегодня — я подберу прекрасный вариант и забронирую столик." if context.user_data.get('language') == 'ru' else "I've saved your choice. You can always change it. Tell me what you'd like today — I'll find a perfect option and book a table for you."
    
    # Удаляем кнопки и показываем сообщение
    await query.edit_message_text(message)

async def check_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'budget' in context.user_data:
        budget = context.user_data['budget']
        message = f"Текущий ценовой диапазон: {'$' * int(budget)}"
        if context.user_data.get('language') != 'ru':
            message = f"Current price range: {'$' * int(budget)}"
    else:
        message = "Ценовой диапазон не выбран"
        if context.user_data.get('language') != 'ru':
            message = "Price range not selected"
    
    await update.message.reply_text(message)
    await show_budget_buttons(update, context)

async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user["id"]
    username = user["username"]

    logger.info("Processing message from %s: %s", username, update.message.text)

    if context.user_data.get('awaiting_language'):
        text = update.message.text.strip()
        # Определяем язык по первому сообщению
        if any(c in text for c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'):
            context.user_data['language'] = 'ru'
        else:
            context.user_data['language'] = 'en'
        context.user_data['awaiting_language'] = False
        
        # Отправляем приветствие на выбранном языке
        welcome_messages = {
            'ru': "Я знаю о ресторанах на Пхукете всё.",
            'en': "I know everything about restaurants in Phuket.",
            'fr': "Je connais tout sur les restaurants de Phuket.",
            'ar': "أعرف كل شيء عن المطاعم في بوكيت.",
            'zh': "我了解普吉岛的所有餐厅。",
            'th': "ผมรู้ทุกอย่างเกี่ยวกับร้านอาหารในภูเก็ต"
        }
        
        welcome_message = welcome_messages.get(context.user_data['language'], welcome_messages['en'])
        await update.message.reply_text(welcome_message)
        
        # Показываем кнопки выбора бюджета
        logger.info("Showing budget buttons for user %s", username)
        try:
            await show_budget_buttons(update, context)
            logger.info("Sent message with keyboard")
        except Exception as e:
            logger.error("Error showing budget buttons: %s", e)
            logger.exception("Full traceback:")
        
        # Инициализируем чат с ChatGPT
        q = "Пользователь выбрал язык. Начни диалог." if context.user_data['language'] == 'ru' else "User selected language. Start the conversation."
        try:
            a, chat_log = ask(q, context.user_data['chat_log'])
            context.user_data['chat_log'] = chat_log
        except Exception as e:
            logger.error("Error in ask: %s", e)
        return

    # Обработка обычного сообщения
    try:
        a, chat_log = ask(update.message.text, context.user_data['chat_log'])
        context.user_data['chat_log'] = chat_log
        await update.message.reply_text(a)
    except Exception as e:
        logger.error("Error in ask: %s", e)
        await update.message.reply_text(
            "Извините, произошла ошибка. Попробуйте еще раз." if context.user_data.get('language') == 'ru'
            else "Sorry, an error occurred. Please try again."
        )

def main():
    app = ApplicationBuilder().token(telegram_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_budget))
    app.add_handler(CallbackQueryHandler(budget_callback, pattern="^budget_"))
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, talk))
    app.run_polling()

if __name__ == '__main__':
    main()