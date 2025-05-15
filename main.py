#!/usr/bin/env python

import logging, os, uuid, json
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from dotenv import load_dotenv
from openai import OpenAI
import psycopg2
from psycopg2.extras import DictCursor
import spacy

# Load environment variables
load_dotenv()

# Читаем версию
with open('version.txt', 'r') as f:
    VERSION = f.read().strip()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"Starting BookTable bot version {VERSION}")

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
        
        # Сохраняем telegram_username отдельно
        telegram_username = username or f"{first_name or ''} {last_name or ''}".strip() or str(user_id)
        logger.info(f"Formed telegram_username: {telegram_username}")
        
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
                SET telegram_username = %s, language = %s 
                WHERE telegram_user_id = %s
                RETURNING client_number
            """
            logger.info(f"Executing update query with params: telegram_username={telegram_username}, language={language}, user_id={user_id}")
            cur.execute(update_query, (telegram_username, language, user_id))
            client_number = cur.fetchone()['client_number']
            logger.info(f"Updated existing user with client_number: {client_number}")
        else:
            # Создаем нового пользователя
            insert_query = """
                INSERT INTO users (telegram_user_id, telegram_username, language)
                VALUES (%s, %s, %s)
                RETURNING client_number
            """
            logger.info(f"Executing insert query with params: user_id={user_id}, telegram_username={telegram_username}, language={language}")
            cur.execute(insert_query, (user_id, telegram_username, language))
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

def ask(q, chat_log=None, language='en'):
    if chat_log is None:
        chat_log = start_convo.copy()
    
    # Добавляем инструкцию о языке в промпт
    language_instruction = f"Please respond in {language} language."
    chat_log = chat_log + [{"role": "user", "content": f"{language_instruction}\n{q}"}]
    
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

# Базовые сообщения на английском
BASE_MESSAGES = {
    'welcome': "I know everything about restaurants in Phuket.",
    'choose_language': "Please choose your language or just type a message — I understand more than 120 languages and will reply in yours!",
    'budget_question': "What price range would you prefer for the restaurant?",
    'budget_saved': "I've saved your choice. You can always change it. Tell me what you'd like today — I'll find a perfect option and book a table for you.",
    'current_budget': "Current price range: {}",
    'no_budget': "Price range not selected",
    'error': "Sorry, an error occurred. Please try again."
}

async def translate_message(message_key: str, language: str, **kwargs) -> str:
    """
    Переводит сообщение на нужный язык с помощью ChatGPT.
    """
    try:
        # Если язык английский, возвращаем оригинальное сообщение
        if language == 'en':
            return BASE_MESSAGES[message_key].format(**kwargs)
            
        # Формируем промпт для перевода
        prompt = f"""Translate the following English message to {language} language. 
        Keep the same meaning and tone. If there are placeholders like {{}}, keep them in the translation.
        Message: {BASE_MESSAGES[message_key]}"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Низкая температура для более точного перевода
            max_tokens=100
        )
        
        translated = response.choices[0].message.content.strip()
        return translated.format(**kwargs)
    except Exception as e:
        logger.error(f"Error translating message: {e}")
        return BASE_MESSAGES[message_key].format(**kwargs)  # Возвращаем оригинальное сообщение в случае ошибки

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
        
        # Сообщения о выборе бюджета на разных языках
        budget_messages = {
            'ru': "С каким средним чеком подберем ресторан?",
            'en': "What price range would you prefer for the restaurant?",
            'fr': "Quelle gamme de prix préférez-vous pour le restaurant ?",
            'ar': "ما هو نطاق السعر الذي تفضله للمطعم؟",
            'zh': "您希望餐厅的价格范围是多少？",
            'th': "คุณต้องการช่วงราคาของร้านอาหารเท่าไหร่?",
            'es': "¿Qué rango de precios prefieres para el restaurante?"
        }
        
        # Получаем актуальный язык пользователя
        lang = context.user_data.get('language', 'en')
        message = budget_messages.get(lang, budget_messages['en'])
        
        await query.message.reply_text(message, reply_markup=reply_markup)
        
        # Инициализируем чат с ChatGPT
        q = "Пользователь выбрал язык. Начни диалог." if lang == 'ru' else "User selected language. Start the conversation."
        try:
            a, chat_log = ask(q, context.user_data['chat_log'], lang)
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
    
    # Получаем актуальный язык пользователя
    lang = context.user_data.get('language', 'en')
    message = await translate_message('budget_question', lang)
    
    await update.message.reply_text(message, reply_markup=reply_markup)

async def budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer(text="", show_alert=False)
    
    # Обработка выбора бюджета
    budget = query.data.split('_')[1]
    
    # Сохраняем выбранный бюджет
    context.user_data['budget'] = budget
    
    # Получаем актуальный язык пользователя
    lang = context.user_data.get('language', 'en')
    message = await translate_message('budget_saved', lang)
    
    # Удаляем кнопки и показываем сообщение
    await query.edit_message_text(message)

async def check_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Получаем актуальный язык пользователя
    lang = context.user_data.get('language', 'en')
    
    if 'budget' in context.user_data:
        budget = context.user_data['budget']
        message = await translate_message('current_budget', lang, budget='$' * int(budget))
    else:
        message = await translate_message('no_budget', lang)
    
    await update.message.reply_text(message)
    await show_budget_buttons(update, context)

# Загружаем модель для определения языка
try:
    nlp = spacy.load("xx_ent_wiki_sm")
    logger.info("SpaCy language detection model loaded successfully")
except Exception as e:
    logger.error(f"Error loading SpaCy model: {e}")
    nlp = None

def detect_language(text):
    """
    Определяет язык текста с помощью ChatGPT.
    Возвращает код языка в формате ISO 639-1.
    """
    try:
        # Запрашиваем у ChatGPT определение языка
        prompt = f"""Определи язык следующего текста и верни только код языка в формате ISO 639-1 (например, 'en' для английского, 'es' для испанского, 'ru' для русского).
        Текст: "{text}"
        Ответ должен содержать только код языка, без дополнительных слов или символов."""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Низкая температура для более точного ответа
            max_tokens=10
        )
        
        lang = response.choices[0].message.content.strip().lower()
        logger.info(f"ChatGPT detected language: {lang}")
        
        # Специальная обработка для языков
        if lang in ['es', 'ca', 'gl']:  # Испанский, каталанский, галисийский
            return 'es'
        elif lang in ['fr', 'oc']:  # Французский, окситанский
            return 'fr'
        elif lang in ['ru', 'uk', 'be']:  # Русский, украинский, белорусский
            return 'ru'
        elif lang in ['zh', 'zh_cn', 'zh_tw']:  # Китайский
            return 'zh'
        elif lang in ['ar', 'fa', 'ur']:  # Арабский, персидский, урду
            return 'ar'
        elif lang in ['th', 'lo']:  # Тайский, лаосский
            return 'th'
            
        return lang
    except Exception as e:
        logger.error(f"Error detecting language with ChatGPT: {e}")
        return 'en'  # По умолчанию английский

async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user["id"]
    username = user["username"]

    logger.info("Processing message from %s: %s", username, update.message.text)

    text = update.message.text.strip()
    detected_lang = detect_language(text)
    logger.info(f"Detected language: {detected_lang}")

    # Если язык отличается от сохранённого — обновляем в базе и в context
    if context.user_data.get('language') != detected_lang:
        context.user_data['language'] = detected_lang
        # Обновляем язык в базе
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            cur.execute("UPDATE users SET language = %s WHERE telegram_user_id = %s", (detected_lang, user.id))
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Updated language in DB to {detected_lang} for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to update language in DB: {e}")

    # Если это первое сообщение после старта (awaiting_language), то приветствие и кнопки
    if context.user_data.get('awaiting_language'):
        context.user_data['awaiting_language'] = False
        # Сохраняем пользователя в базу данных
        client_number = save_user_to_db(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=detected_lang
        )
        logger.info(f"User saved with client_number: {client_number}")
        
        # Приветствие
        welcome_message = await translate_message('welcome', detected_lang)
        await update.message.reply_text(welcome_message)
        
        # Кнопки бюджета
        await show_budget_buttons(update, context)
        
        # Инициализация чата с ChatGPT
        q = "User selected language. Start the conversation."
        try:
            a, chat_log = ask(q, context.user_data['chat_log'], detected_lang)
            context.user_data['chat_log'] = chat_log
        except Exception as e:
            logger.error("Error in ask: %s", e)
        return

    # Все остальные сообщения — обычный диалог
    try:
        a, chat_log = ask(update.message.text, context.user_data['chat_log'], detected_lang)
        context.user_data['chat_log'] = chat_log
        await update.message.reply_text(a)
    except Exception as e:
        logger.error("Error in ask: %s", e)
        error_message = await translate_message('error', detected_lang)
        await update.message.reply_text(error_message)

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