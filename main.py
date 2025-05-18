#!/usr/bin/env python

import logging, os, uuid, json
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, MenuButtonCommands
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.constants import ChatAction
from dotenv import load_dotenv
from openai import OpenAI
import psycopg2
from psycopg2.extras import DictCursor
from geopy.geocoders import Nominatim
import asyncio
from math import radians, sin, cos, sqrt, atan2
import traceback

# Load environment variables
load_dotenv()

# Читаем версию
with open('version.txt', 'r') as f:
    VERSION = f.read().strip()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,  # Меняем уровень на DEBUG
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Устанавливаем уровень DEBUG для логгера
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
    
    # Формируем промпт для ChatGPT
    prompt = f"Пользователь спросил: '{q}'. Если речь идет о ресторанах, верни системный ответ в формате ### и перечисли ключевые аспекты через запятую."
    chat_log = chat_log + [{"role": "user", "content": prompt}]
    
    logger.debug(f"Sending prompt to ChatGPT: {chat_log}")
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=chat_log,
        temperature=0.7,
        max_tokens=1000
    )
    
    answer = response.choices[0].message.content
    logger.debug(f"Received response from ChatGPT: {answer}")
    chat_log = chat_log + [{"role": "assistant", "content": answer}]
    return answer, chat_log

def append_interaction_to_chat_log(q, a, chat_log=None):
    if chat_log is None:
        chat_log = start_convo.copy()
    chat_log = chat_log + [{"role": "user", "content": q}]
    chat_log = chat_log + [{"role": "assistant", "content": a}]
    return chat_log

# Список районов Пхукета
PHUKET_AREAS = {
    'chalong': 'Чалонг',
    'patong': 'Паттонг',
    'kata': 'Ката',
    'karon': 'Карон',
    'phuket_town': 'Пхукет-таун',
    'kamala': 'Камала',
    'rawai': 'Равай',
    'nai_harn': 'Най Харн',
    'bang_tao': 'Банг Тао',
    'other': 'Другой'
}

# Координаты центров районов Пхукета (примерные)
PHUKET_AREAS_COORDS = {
    'chalong': (7.8314, 98.3381),
    'patong': (7.8966, 98.2965),
    'kata': (7.8210, 98.2943),
    'karon': (7.8486, 98.2948),
    'phuket_town': (7.8804, 98.3923),
    'kamala': (7.9506, 98.2807),
    'rawai': (7.7796, 98.3281),
    'nai_harn': (7.7726, 98.3166),
    'bang_tao': (7.9936, 98.2933)
}

# Базовые сообщения на английском
BASE_MESSAGES = {
    'welcome': "I know everything about restaurants in Phuket.",
    'choose_language': "Please choose your language or just type a message — I understand more than 120 languages and will reply in yours!",
    'budget_question': "What price range would you prefer for the restaurant?",
    'budget_saved': "I've saved your choice. You can always change it. Tell me what you'd like today — I'll find a perfect option and book a table for you.",
    'current_budget': "Current price range: {}",
    'no_budget': "Price range not selected",
    'error': "Sorry, an error occurred. Please try again.",
    # Новые сообщения для локации
    'location_question': "Choose your location:",
    'location_near': "NEAR ME",
    'location_area': "CHOOSE AREA",
    'location_any': "ANYWHERE",
    'location_send': "Please send your location:",
    'location_thanks': "Thank you! Now I know your location.",
    'area_question': "Choose area:",
    'area_selected': "Selected area: {}",
    'location_any_confirmed': "Okay, I'll search restaurants all over the island.",
    'location_error': "Sorry, I couldn't get your location. Please try again or choose another option.",
    'other_area_prompt': "Please specify the area or location you're interested in."
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
        logger.debug(f"[language_callback] Received callback query: {query.data}")
        print("[language_callback] Received callback query")
        
        # Получаем выбранный язык из callback_data
        lang = query.data.split('_')[1]
        logger.debug(f"[language_callback] Selected language: {lang}")
        print(f"[language_callback] Selected language: {lang}")
        
        context.user_data['language'] = lang
        context.user_data['awaiting_language'] = False
        
        # Удаляем сообщение с кнопками выбора языка
        await query.message.delete()
        logger.debug("[language_callback] Deleted language selection message")
        print("[language_callback] Deleted language selection message")
        
        # Сохраняем пользователя в базу данных
        user = update.effective_user
        logger.debug(f"[language_callback] Processing user: {user.id} ({user.username})")
        print(f"[language_callback] Processing user: {user.id} ({user.username})")
        
        client_number = save_user_to_db(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=lang
        )
        logger.debug(f"[language_callback] User saved with client_number: {client_number}")
        print(f"[language_callback] User saved with client_number: {client_number}")
        
        # Отправляем приветствие на выбранном языке
        welcome_messages = {
            'ru': "Я знаю о ресторанах на Пхукете всё.",  # Возвращаем строку в приветственное сообщение
            'en': "I know everything about restaurants in Phuket.",
            'fr': "Je connais tout sur les restaurants de Phuket.",
            'ar': "أعرف كل شيء عن المطاعم في بوكيت.",
            'zh': "我了解普吉岛的所有餐厅。",
            'th': "ผมรู้ทุกอย่างเกี่ยวกับร้านอาหารในภูเก็ต"
        }
        
        welcome_message = welcome_messages.get(lang, welcome_messages['en'])
        logger.debug(f"[language_callback] Sending welcome message: {welcome_message}")
        print(f"[language_callback] Sending welcome message: {welcome_message}")
        await query.message.reply_text(welcome_message)
        logger.debug("[language_callback] Welcome message sent")
        print("[language_callback] Welcome message sent")
        
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
            'th': "คุณต้องการช่วงราคาของร้านอาหารเท่าไหร่?"
        }
        
        message = budget_messages.get(lang, budget_messages['en'])
        logger.debug(f"[language_callback] Sending budget message: {message}")
        print(f"[language_callback] Sending budget message: {message}")
        await query.message.reply_text(message, reply_markup=reply_markup)
        logger.debug("[language_callback] Budget message sent")
        print("[language_callback] Budget message sent")
        
    except Exception as e:
        logger.error(f"Error in language_callback: {e}")
        print(f"[language_callback] Exception: {e}")
        await query.message.reply_text("Sorry, an error occurred. Please try again.")

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
    logger.debug(f"[budget_callback] Received callback query: {query.data}")
    print("[budget_callback] Received callback query")
    
    # Сразу включаем эффект печатания
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
    
    # Сохраняем выбор бюджета
    budget = query.data.split('_')[1]
    context.user_data['budget'] = budget
    logger.debug(f"[budget_callback] Budget set: {budget}")
    print(f"[budget_callback] Budget set: {budget}")
    
    language = context.user_data.get('language', 'en')
    
    # Подготавливаем сообщение о сохранении бюджета
    budget_saved = await translate_message('budget_saved', language)
    
    # Удаляем сообщение с кнопками бюджета
    await query.message.delete()
    
    # Удаляем предыдущее сообщение (приветствие)
    try:
        # Получаем ID чата
        chat_id = query.message.chat_id
        # Получаем ID сообщения с кнопками
        message_id = query.message.message_id
        # Удаляем предыдущее сообщение (message_id - 1)
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id-1)
    except Exception as e:
        logger.error(f"Error deleting previous message: {e}")
    
    await query.answer()
    logger.debug("[budget_callback] Query answered")
    print("[budget_callback] Query answered")
    
    # Отправляем сообщение о сохранении бюджета
    logger.debug(f"[budget_callback] Sending budget_saved message: {budget_saved}")
    print(f"[budget_callback] Sending budget_saved message: {budget_saved}")
    await query.message.reply_text(budget_saved)
    logger.debug("[budget_callback] budget_saved message sent")
    print("[budget_callback] budget_saved message sent")
    
    # Устанавливаем флаг, что ждем ответа пользователя
    context.user_data['awaiting_budget_response'] = True

async def location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора местоположения"""
    query = update.callback_query
    await query.answer()
    
    # Удаляем сообщение с кнопками выбора локации
    await query.message.delete()
    
    language = context.user_data.get('language', 'en')
    
    if query.data == 'location_near':
        # Включаем эффект печатания
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)  # Добавляем небольшую задержку
        
        # Показываем кнопку только для мобильных
        keyboard = [[KeyboardButton("📍 Мое местоположение", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await query.message.reply_text(
            "Пожалуйста, поделитесь вашим текущим местоположением, я подберу ресторан неподалеку. Или введите район текстом.",
            reply_markup=reply_markup
        )
        # Устанавливаем флаг ожидания локации или района
        context.user_data['awaiting_location_or_area'] = True
        return
    
    elif query.data == 'location_area':
        # Включаем эффект печатания
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)  # Добавляем небольшую задержку
        
        # Создаем кнопки районов в два ряда
        areas = list(PHUKET_AREAS.items())
        keyboard = []
        for i in range(0, len(areas), 2):
            row = []
            row.append(InlineKeyboardButton(areas[i][1], callback_data=f'area_{areas[i][0]}'))
            if i + 1 < len(areas):
                row.append(InlineKeyboardButton(areas[i+1][1], callback_data=f'area_{areas[i+1][0]}'))
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите район из списка или напишите мне более точное место", reply_markup=reply_markup)
    
    elif query.data == 'location_any':
        # Включаем эффект печатания
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)  # Добавляем небольшую задержку
        
        context.user_data['location'] = 'any'
        await query.message.reply_text("Хорошо, я буду искать рестораны по всему острову.")
        # Инициализируем чат с ChatGPT
        q = "Пользователь выбрал язык, бюджет и любое место на острове. Начни диалог." if language == 'ru' else "User selected language, budget and any location on the island. Start the conversation."
        try:
            a, chat_log = ask(q, context.user_data['chat_log'], language)
            context.user_data['chat_log'] = chat_log
            await update.message.reply_text(a)
        except Exception as e:
            logger.error(f"Error in ask: {e}")
            error_message = await translate_message('error', language)
            await update.message.reply_text(error_message)

async def area_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    # Удаляем сообщение с кнопками выбора района
    await query.message.delete()
    language = context.user_data.get('language', 'ru')
    area_id = query.data.split('_')[1].replace('-', '_')
    if area_id == 'other':
        # Если выбран "Другой", просим пользователя ввести место
        other_message = "Пожалуйста, напишите название района или места, где вы хотите найти ресторан."
        if language != 'ru':
            other_message = await translate_message('other_area_prompt', language)
        await query.message.reply_text(other_message)
        context.user_data['awaiting_area_input'] = True
        return
    area_name = PHUKET_AREAS[area_id]
    context.user_data['location'] = {'area': area_id, 'name': area_name}
    # Убираю геокодирование, обновление координат в базе и ChatGPT-диалог
    # Показываем только список ресторанов
    await show_pretty_restaurants(update, context)

# Новая функция для красивого вывода ресторанов
async def show_pretty_restaurants(update, context):
    """Показывает красиво оформленный список подходящих ресторанов"""
    location = context.user_data.get('location')
    budget = context.user_data.get('budget')
    language = context.user_data.get('language', 'ru')

    # Для строкового фильтра по бюджету
    budget_map = {
        '1': '$',
        '2': '$$',
        '3': '$$$',
        '4': '$$$$'
    }
    budget_str = budget_map.get(budget, None)

    # ДОП. ОТЛАДКА: выводим, что ищем
    # await update.effective_chat.send_message(f"DEBUG: budget_str={budget_str}, location={location}")

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)

        found_other_price = False
        other_price_rows = []
        
        if location == 'any':
            if budget_str:
                await update.effective_chat.send_message(f"DEBUG: SQL=SELECT name, average_check FROM restaurants WHERE average_check = '{budget_str}' AND active = 'true' ORDER BY name")
                cur.execute(
                    "SELECT name, average_check FROM restaurants WHERE average_check = %s AND active = 'true' ORDER BY name",
                    (budget_str,)
                )
                rows = cur.fetchall()
                # Проверяем, есть ли другие рестораны в других ценовых категориях
                cur.execute(
                    "SELECT name, average_check FROM restaurants WHERE active = 'true' AND average_check != %s ORDER BY name",
                    (budget_str,)
                )
                other_price_rows = cur.fetchall()
                found_other_price = bool(other_price_rows)
            else:
                cur.execute(
                    "SELECT name, average_check FROM restaurants WHERE active = 'true' ORDER BY name"
                )
                rows = cur.fetchall()
        elif isinstance(location, dict) and 'area' in location:
            if budget_str:
                smart_area = location['area'].lower().replace(' ', '').replace(',', '')
                smart_name = location['name'].lower().replace(' ', '').replace(',', '')
                # await update.effective_chat.send_message(f"DEBUG: smart_area={smart_area}, smart_name={smart_name}")
                # await update.effective_chat.send_message(f"DEBUG: SQL=SELECT name, average_check, location FROM restaurants WHERE (REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s OR REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s) AND average_check::text = '{budget_str}' AND active = 'true' ORDER BY name")
                # await update.effective_chat.send_message(f"DEBUG: params=('%{smart_area}%', '%{smart_name}%', '{budget_str}')")
                cur.execute(
                    """
                    SELECT name, average_check, location FROM restaurants
                    WHERE (REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s OR REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s)
                    AND average_check::text = %s AND active ILIKE 'true'
                    ORDER BY name
                    """,
                    (f"%{smart_area}%", f"%{smart_name}%", budget_str)
                )
                rows = cur.fetchall()
                # Проверяем, есть ли другие рестораны в этом районе с другим чеком
                cur.execute(
                    """
                    SELECT name, average_check, location FROM restaurants
                    WHERE (REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s OR REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s)
                    AND average_check::text != %s AND active ILIKE 'true'
                    ORDER BY name
                    """,
                    (f"%{smart_area}%", f"%{smart_name}%", budget_str)
                )
                other_price_rows = cur.fetchall()
                found_other_price = bool(other_price_rows)
            else:
                smart_area = location['area'].lower().replace(' ', '').replace(',', '')
                smart_name = location['name'].lower().replace(' ', '').replace(',', '')
                cur.execute(
                    """
                    SELECT name, average_check, location FROM restaurants
                    WHERE (REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s OR REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s)
                    AND active ILIKE 'true'
                    ORDER BY name
                    """,
                    (f"%{smart_area}%", f"%{smart_name}%")
                )
                rows = cur.fetchall()
        elif isinstance(location, dict) and 'lat' in location and 'lon' in location:
            rows = []
        else:
            rows = []

        # Отладочный вывод результата SQL-запроса
        # debug_sql_result = f"DEBUG SQL rows: {rows}"
        # await update.effective_chat.send_message(debug_sql_result)

        if not rows and found_other_price and other_price_rows:
            area_name = location['name'] if isinstance(location, dict) and 'name' in location else 'выбранном районе'
            msg = f"Увы, но в районе {area_name} нет ресторанов со средним чеком {budget_str}, которые соответствуют высоким стандартам качества BookTable.AI. Но есть рестораны в другой ценовой категории. Посмотрите их или поищем в другом районе?\n\n"
            for r in other_price_rows:
                msg += f"• {r['name']} — {r['average_check']}\n"
            keyboard = [
                [InlineKeyboardButton("ПОСМОТРИМ", callback_data="show_other_price")],
                [InlineKeyboardButton("ДРУГОЙ РАЙОН", callback_data="choose_area")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.effective_chat.send_message(msg, reply_markup=reply_markup)
            return
        elif not rows:
            msg = "К сожалению, в этом районе пока нет подходящих ресторанов по выбранным параметрам. Попробуйте выбрать другой район или изменить бюджет."
            await update.effective_chat.send_message(msg)
            return
        else:
            # Если найдено 1-3 ресторана — выводим расширенную информацию и AI-комментарий
            if 1 <= len(rows) <= 3:
                # Получаем подробную информацию о ресторанах
                restaurant_ids = tuple([r['name'] for r in rows])
                # Формируем SQL для получения кухни и описания
                cur2 = conn.cursor(cursor_factory=DictCursor)
                names = tuple([r['name'] for r in rows])
                # Используем параметризованный запрос для избежания ошибок с апострофами
                cur2.execute(
                    """
                    SELECT name, average_check, cuisine, features, atmosphere, story_or_concept
                    FROM restaurants
                    WHERE name IN %s
                    """,
                    (names,)
                )
                details = {r['name']: r for r in cur2.fetchall()}
                msg = "Рестораны, которые мы рекомендуем в этом районе:\n\n"
                for r in rows:
                    d = details.get(r['name'], {})
                    cuisine = d.get('cuisine') or ''
                    features = d.get('features')
                    if isinstance(features, list):
                        features = ', '.join(features)
                    elif features is None:
                        features = ''
                    atmosphere = d.get('atmosphere') or ''
                    story = d.get('story_or_concept') or ''
                    desc = features or atmosphere or story
                    # Переводим cuisine и описание только через OpenAI, явно указывая язык
                    if language != 'en':
                        try:
                            if cuisine:
                                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                                cuisine = (await ask(f"Переведи на {language} (только тип кухни, без лишних слов): {cuisine}", None, language))[0]
                            if desc:
                                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                                desc = (await ask(f"Переведи на {language} (только краткое описание ресторана, без лишних слов): {desc}", None, language))[0]
                        except Exception as e:
                            logger.error(f"Ошибка перевода описания ресторана: {e}")
                    msg += f"• {r['name']} — {r['average_check']}\n"
                    if cuisine:
                        msg += f"{cuisine}\n"
                    if desc:
                        msg += f"{desc}\n"
                    msg += "\n"
                await update.effective_chat.send_message(msg)
                # AI-комментарий
                try:
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                    user_history = context.user_data.get('chat_log', [])
                    user_wish = context.user_data.get('last_user_wish', '')
                    rest_summaries = []
                    for r in rows:
                        d = details.get(r['name'], {})
                        cuisine = d.get('cuisine') or ''
                        features = d.get('features')
                        if isinstance(features, list):
                            features = ', '.join(features)
                        elif features is None:
                            features = ''
                        atmosphere = d.get('atmosphere') or ''
                        story = d.get('story_or_concept') or ''
                        desc = features or atmosphere or story
                        # Переводим cuisine и описание для AI только через OpenAI
                        if language != 'en':
                            try:
                                if cuisine:
                                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                                    cuisine = (await ask(f"Переведи на {language} (только тип кухни, без лишних слов): {cuisine}", None, language))[0]
                                if desc:
                                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                                    desc = (await ask(f"Переведи на {language} (только краткое описание ресторана, без лишних слов): {desc}", None, language))[0]
                            except Exception as e:
                                logger.error(f"Ошибка перевода описания ресторана: {e}")
                        rest_summaries.append(f"{r['name']} — {cuisine}. {desc}")
                    rest_text = '\n'.join(rest_summaries)
                    ban_meal_words = "Не используй слова 'завтрак', 'обед', 'ужин', 'бранч' и любые конкретные приёмы пищи. Используй только нейтральные формулировки: 'вашему визиту', 'посещению', 'отдыху' и т.д."
                    wish_part = f"Учитывай пожелание пользователя: '{user_wish}'. Используй только факты из базы (кухня, особенности, блюда), не выдумывай ничего." if user_wish else "Используй только факты из базы (кухня, особенности, блюда), не выдумывай ничего."
                    if len(rows) == 1:
                        prompt = (
                            f"Пользователь выбрал район и бюджет, вот его история: {user_history}. "
                            f"Вот ресторан, который мы рекомендуем: {rest_text}. "
                            f"{wish_part} Сделай заманчивое, мотивирующее сообщение (1-2 предложения) про этот ресторан, подчеркни его преимущества, предложи забронировать или задать вопросы. Не используй стандартные приветствия, не повторяй фразы типа 'Я знаю о ресторанах...' или 'Просто расскажите...'. {ban_meal_words} Пиши на языке пользователя ({language}), не упоминай слово 'бот', не повторяй название ресторана."
                        )
                    else:
                        prompt = (
                            f"Пользователь выбрал район и бюджет, вот его история: {user_history}. "
                            f"Вот список ресторанов, которые мы рекомендуем: {rest_text}. "
                            f"{wish_part} Помоги пользователю определиться с выбором, кратко подскажи отличия, предложи выбрать или задать вопросы. Не используй стандартные приветствия, не повторяй фразы типа 'Я знаю о ресторанах...' или 'Просто расскажите...'. {ban_meal_words} Пиши на языке пользователя ({language}), не упоминай слово 'бот', не повторяй названия ресторанов."
                        )
                    ai_msg, chat_log = ask(prompt, context.user_data.get('chat_log'), language)
                    context.user_data['chat_log'] = chat_log
                    await update.effective_chat.send_message(ai_msg)
                except Exception as e:
                    logger.error(f"Ошибка генерации AI-комментария: {e}")
                return
            # Если больше 3 ресторанов — обычный список
            msg = "Рестораны, которые мы рекомендуем в этом районе:\n\n"
            for r in rows:
                msg += f"• {r['name']} — {r['average_check']}\n"
            await update.effective_chat.send_message(msg)
            return
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in show_pretty_restaurants: {e}")
        await update.effective_chat.send_message(f"Ошибка поиска ресторанов: {e}")

def get_nearest_area(lat, lon):
    min_dist = float('inf')
    nearest_area = None
    for area, (alat, alon) in PHUKET_AREAS_COORDS.items():
        dlat = radians(lat - alat)
        dlon = radians(lon - alon)
        a = sin(dlat/2)**2 + cos(radians(lat)) * cos(radians(alat)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        dist = 6371 * c  # расстояние в км
        if dist < min_dist:
            min_dist = dist
            nearest_area = area
    return nearest_area

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        logger.info(f"handle_location вызван. update.message: {update.message}")
        # Удаляем отладочный вывод пользователю
        # await update.message.reply_text(f"DEBUG: update.message={update.message}")
        if not hasattr(update.message, 'location') or update.message.location is None:
            error_text = "Похоже, вы не разрешили Telegram доступ к геолокации. Пожалуйста, включите доступ к геолокации для Telegram в настройках телефона и попробуйте ещё раз."
            if update.message:
                await update.message.reply_text(error_text)
            else:
                await context.bot.send_message(chat_id=update.effective_user.id, text=error_text)
            return
        location = update.message.location
        context.user_data['location'] = {
            'lat': location.latitude,
            'lon': location.longitude
        }
        context.user_data['location_received'] = True
        language = context.user_data.get('language', 'en')
        # Получаем адрес по координатам
        geolocator = Nominatim(user_agent="booktable_bot")
        try:
            location_data = geolocator.reverse(f"{location.latitude}, {location.longitude}")
            if location_data:
                context.user_data['location']['address'] = location_data.address
                # Сохраняем координаты в базу
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
            logger.error(f"Error getting address from coordinates: {e}")
        # Определяем ближайший район
        nearest_area = get_nearest_area(location.latitude, location.longitude)
        if nearest_area:
            area_name = PHUKET_AREAS[nearest_area]
            context.user_data['location'] = {'area': nearest_area, 'name': area_name}
            # await update.message.reply_text(f"Определён район: {area_name}")
            await show_pretty_restaurants(update, context)
        else:
            await update.message.reply_text("Не удалось определить район по координатам. Пожалуйста, выберите район вручную.")
        # Убираю вызов debug_show_restaurants и лишние отладочные сообщения
        # Инициализируем чат с ChatGPT
        q = "Пользователь выбрал язык, бюджет и отправил свою локацию. Начни диалог." if language == 'ru' else "User selected language, budget and sent their location. Start the conversation."
        try:
            a, chat_log = ask(q, context.user_data['chat_log'], language)
            context.user_data['chat_log'] = chat_log
            await update.message.reply_text(a)
        except Exception as e:
            logger.error(f"Error in ask: {e}")
            error_message = await translate_message('error', language)
            await update.message.reply_text(error_message)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Ошибка при получении локации: {e}\n{tb}")
        error_text = f"Ошибка при получении локации: {e}\n{tb}\nПожалуйста, попробуйте ещё раз или выберите район вручную."
        if update.message:
            await update.message.reply_text(error_text)
        else:
            await context.bot.send_message(chat_id=update.effective_user.id, text=error_text)

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

    # --- ДОБАВЛЕНО: обработка ошибочного ввода района для любого текста ---
    # Проверяем, не команда ли это и не про еду ли текст
    restaurant_keywords = ['мясо', 'рыба', 'морепродукты', 'тайская', 'итальянская', 'японская', 
                         'китайская', 'индийская', 'вегетарианская', 'веганская', 'барбекю', 
                         'стейк', 'суши', 'паста', 'пицца', 'бургер', 'фастфуд', 'кафе', 
                         'ресторан', 'кухня', 'еда', 'ужин', 'обед', 'завтрак', 'brunch']
    text_lower = text.lower()
    is_restaurant_related = any(keyword in text_lower for keyword in restaurant_keywords)
    is_command = text_lower.startswith('/')
    # Если это не команда и не про еду, пробуем сопоставить с районом
    if not is_command and not is_restaurant_related and not context.user_data.get('awaiting_location_or_area') and not context.user_data.get('awaiting_area_input'):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT location FROM restaurants WHERE location IS NOT NULL AND location != ''")
            all_locations = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching locations from DB: {e}")
            await update.message.reply_text("Ошибка при получении списка локаций из базы данных.")
            return
        prompt = (
            f"Пользователь ввёл: '{text}'. Вот список всех локаций из базы данных: {all_locations}. "
            "Определи, какая локация из базы наиболее соответствует пользовательскому вводу. "
            "Верни только точное значение из списка, без пояснений. Если ничего не подходит, верни 'NO_MATCH'."
        )
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50
            )
            matched_location = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error in OpenAI location match: {e}")
            await update.message.reply_text("Ошибка при обработке локации через AI.")
            return
        if matched_location == 'NO_MATCH':
            # Показываем список районов на выбор
            areas = list(PHUKET_AREAS.items())
            keyboard = []
            for i in range(0, len(areas), 2):
                row = []
                row.append(InlineKeyboardButton(areas[i][1], callback_data=f'area_{areas[i][0]}'))
                if i + 1 < len(areas):
                    row.append(InlineKeyboardButton(areas[i+1][1], callback_data=f'area_{areas[i+1][0]}'))
                keyboard.append(row)
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Пожалуйста, выберите район из списка:", reply_markup=reply_markup)
            return
        # Сохраняем найденную локацию и ищем рестораны
        context.user_data['location'] = {'area': matched_location, 'name': matched_location}
        await update.message.reply_text(f"Отлично, поищем в районе {matched_location}. Что бы вам хотелось сегодня покушать? Я подберу прекрасный вариант и забронирую столик.")
        await show_pretty_restaurants(update, context)
        return
    # --- КОНЕЦ ДОБАВЛЕНИЯ ---

    # Если язык отличается от сохранённого — обновляем в базе и в context
    if context.user_data.get('language') != detected_lang:
        context.user_data['language'] = detected_lang
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
        client_number = save_user_to_db(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=detected_lang
        )
        logger.info(f"User saved with client_number: {client_number}")
        
        # Включаем эффект печатания
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)  # Добавляем небольшую задержку
        
        welcome_message = await translate_message('welcome', detected_lang)
        await update.message.reply_text(welcome_message)
        
        await show_budget_buttons(update, context)
        return

    # Если это ответ после выбора бюджета
    if context.user_data.get('awaiting_budget_response'):
        context.user_data['awaiting_budget_response'] = False
        # Включаем эффект печатания
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)  # Добавляем небольшую задержку
        # Проверяем, относится ли ответ к ресторанам
        restaurant_keywords = ['мясо', 'рыба', 'морепродукты', 'тайская', 'итальянская', 'японская', 
                             'китайская', 'индийская', 'вегетарианская', 'веганская', 'барбекю', 
                             'стейк', 'суши', 'паста', 'пицца', 'бургер', 'фастфуд', 'кафе', 
                             'ресторан', 'кухня', 'еда', 'ужин', 'обед', 'завтрак', 'brunch']
        text_lower = text.lower()
        is_restaurant_related = any(keyword in text_lower for keyword in restaurant_keywords)
        # Сохраняем последнее пожелание пользователя
        context.user_data['last_user_wish'] = text
        if is_restaurant_related:
            # Показываем кнопки выбора локации в одну строку
            keyboard = [[
                InlineKeyboardButton("РЯДОМ", callback_data='location_near'),
                InlineKeyboardButton("РАЙОН", callback_data='location_area'),
                InlineKeyboardButton("ВЕЗДЕ", callback_data='location_any')
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            location_message = "Подберу для Вас отличный ресторан! Поискать поблизости, в другом районе или в любом месте на Пхукете?"
            await update.message.reply_text(location_message, reply_markup=reply_markup)
            return

        # Если ответ не о ресторанах - используем ChatGPT для создания уникального ответа
        try:
            # Используем более гибкий и контекстуальный запрос для ChatGPT
            flexible_prompt = f"Пользователь спросил: '{text}'. Ответь остроумно и вежливо, затем плавно верни разговор к бронированию ресторана."
            a, chat_log = ask(flexible_prompt, context.user_data['chat_log'], detected_lang)
            context.user_data['chat_log'] = chat_log
            await update.message.reply_text(a)
        except Exception as e:
            logger.error(f"Error in ask: {e}")
            error_message = await translate_message('error', detected_lang)
            await update.message.reply_text(error_message)
        return

    # Все остальные сообщения — обычный диалог
    try:
        # Включаем эффект печатания
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)  # Добавляем небольшую задержку
        
        a, chat_log = ask(update.message.text, context.user_data['chat_log'], detected_lang)
        context.user_data['chat_log'] = chat_log
        await update.message.reply_text(a)
    except Exception as e:
        logger.error("Error in ask: %s", e)
        error_message = await translate_message('error', detected_lang)
        await update.message.reply_text(error_message)

async def check_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает текущий выбранный бюджет"""
    language = context.user_data.get('language', 'en')
    budget = context.user_data.get('budget')
    
    if budget:
        message = await translate_message('current_budget', language, budget=budget)
    else:
        message = await translate_message('no_budget', language)
    
    await update.message.reply_text(message)

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перезапуск бота: сброс состояния и стартовое приветствие"""
    # Сброс всех пользовательских данных
    context.user_data.clear()
    # Приветственное сообщение и меню, как при /start
    await start(update, context)

async def set_bot_commands(app):
    await app.bot.set_my_commands([
        ("restart", "Перезапустить бота")
    ])
    await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

async def choose_area_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await query.message.reply_text("Выберите район из списка или напишите мне более точное место", reply_markup=reply_markup)

# --- Новый обработчик для кнопки "ПОСМОТРИМ" ---
async def show_other_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    # Для строкового фильтра по бюджету
    budget_map = {
        '1': '$',
        '2': '$$',
        '3': '$$$',
        '4': '$$$$'
    }
    budget_str = budget_map.get(budget, None)
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        if isinstance(location, dict) and 'area' in location:
            smart_area = location['area'].lower().replace(' ', '').replace(',', '')
            smart_name = location['name'].lower().replace(' ', '').replace(',', '')
            cur.execute(
                """
                SELECT name, average_check, location FROM restaurants
                WHERE (REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s OR REPLACE(REPLACE(LOWER(location), ' ', ''), ',', '') ILIKE %s)
                AND average_check::text != %s AND active ILIKE 'true'
                ORDER BY name
                """,
                (f"%{smart_area}%", f"%{smart_name}%", budget_str)
            )
            rows = cur.fetchall()
            if not rows:
                await update.effective_chat.send_message("В этом районе нет ресторанов в других ценовых категориях. Попробуйте выбрать другой район.")
                return
            # Получаем подробную информацию о ресторанах
            cur2 = conn.cursor(cursor_factory=DictCursor)
            names = tuple([r['name'] for r in rows])
            # Используем параметризованный запрос для избежания ошибок с апострофами
            cur2.execute(
                """
                SELECT name, average_check, cuisine, features, atmosphere, story_or_concept
                FROM restaurants
                WHERE name IN %s
                """,
                (names,)
            )
            details = {r['name']: r for r in cur2.fetchall()}
            msg = "Рестораны в этом районе с другим средним чеком:\n\n"
            for r in rows:
                d = details.get(r['name'], {})
                cuisine = d.get('cuisine') or ''
                features = d.get('features')
                if isinstance(features, list):
                    features = ', '.join(features)
                elif features is None:
                    features = ''
                atmosphere = d.get('atmosphere') or ''
                story = d.get('story_or_concept') or ''
                desc = features or atmosphere or story
                # Переводим cuisine и описание только через OpenAI, явно указывая язык
                if language != 'en':
                    try:
                        if cuisine:
                            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                            cuisine = (await ask(f"Переведи на {language} (только тип кухни, без лишних слов): {cuisine}", None, language))[0]
                        if desc:
                            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                            desc = (await ask(f"Переведи на {language} (только краткое описание ресторана, без лишних слов): {desc}", None, language))[0]
                    except Exception as e:
                        logger.error(f"Ошибка перевода описания ресторана: {e}")
                msg += f"• {r['name']} — {r['average_check']}\n"
                if cuisine:
                    msg += f"{cuisine}\n"
                if desc:
                    msg += f"{desc}\n"
                msg += "\n"
            await update.effective_chat.send_message(msg)
            # AI-комментарий
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                user_history = context.user_data.get('chat_log', [])
                user_wish = context.user_data.get('last_user_wish', '')
                rest_summaries = []
                for r in rows:
                    d = details.get(r['name'], {})
                    cuisine = d.get('cuisine') or ''
                    features = d.get('features')
                    if isinstance(features, list):
                        features = ', '.join(features)
                    elif features is None:
                        features = ''
                    atmosphere = d.get('atmosphere') or ''
                    story = d.get('story_or_concept') or ''
                    desc = features or atmosphere or story
                    # Переводим cuisine и описание для AI только через OpenAI
                    if language != 'en':
                        try:
                            if cuisine:
                                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                                cuisine = (await ask(f"Переведи на {language} (только тип кухни, без лишних слов): {cuisine}", None, language))[0]
                            if desc:
                                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                                desc = (await ask(f"Переведи на {language} (только краткое описание ресторана, без лишних слов): {desc}", None, language))[0]
                        except Exception as e:
                            logger.error(f"Ошибка перевода описания ресторана: {e}")
                    rest_summaries.append(f"{r['name']} — {cuisine}. {desc}")
                rest_text = '\n'.join(rest_summaries)
                ban_meal_words = "Не используй слова 'завтрак', 'обед', 'ужин', 'бранч' и любые конкретные приёмы пищи. Используй только нейтральные формулировки: 'вашему визиту', 'посещению', 'отдыху' и т.д."
                wish_part = f"Учитывай пожелание пользователя: '{user_wish}'. Используй только факты из базы (кухня, особенности, блюда), не выдумывай ничего." if user_wish else "Используй только факты из базы (кухня, особенности, блюда), не выдумывай ничего."
                if len(rows) == 1:
                    prompt = (
                        f"Пользователь выбрал район и бюджет, вот его история: {user_history}. "
                        f"Вот ресторан, который мы рекомендуем: {rest_text}. "
                        f"{wish_part} Сделай заманчивое, мотивирующее сообщение (1-2 предложения) про этот ресторан, подчеркни его преимущества, предложи забронировать или задать вопросы. Не используй стандартные приветствия, не повторяй фразы типа 'Я знаю о ресторанах...' или 'Просто расскажите...'. {ban_meal_words} Пиши на языке пользователя ({language}), не упоминай слово 'бот', не повторяй название ресторана."
                    )
                else:
                    prompt = (
                        f"Пользователь выбрал район и бюджет, вот его история: {user_history}. "
                        f"Вот список ресторанов, которые мы рекомендуем: {rest_text}. "
                        f"{wish_part} Помоги пользователю определиться с выбором, кратко подскажи отличия, предложи выбрать или задать вопросы. Не используй стандартные приветствия, не повторяй фразы типа 'Я знаю о ресторанах...' или 'Просто расскажите...'. {ban_meal_words} Пиши на языке пользователя ({language}), не упоминай слово 'бот', не повторяй названия ресторанов."
                    )
                ai_msg, chat_log = ask(prompt, context.user_data.get('chat_log'), language)
                context.user_data['chat_log'] = chat_log
                await update.effective_chat.send_message(ai_msg)
            except Exception as e:
                logger.error(f"Ошибка генерации AI-комментария: {e}")
            return
        else:
            await update.effective_chat.send_message("Ошибка: не удалось определить район для поиска ресторанов.")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка в show_other_price_callback: {e}")
        await update.effective_chat.send_message(f"Ошибка поиска ресторанов: {e}")

def main():
    app = ApplicationBuilder().token(telegram_token).build()
    
    # Базовые команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("filter", check_budget))
    
    # Обработчики callback-запросов
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(budget_callback, pattern="^budget_"))
    app.add_handler(CallbackQueryHandler(location_callback, pattern="^location_"))
    app.add_handler(CallbackQueryHandler(area_callback, pattern="^area_"))
    app.add_handler(CallbackQueryHandler(choose_area_callback, pattern="^choose_area$"))
    # Новый обработчик для кнопки ПОСМОТРИМ
    app.add_handler(CallbackQueryHandler(show_other_price_callback, pattern="^show_other_price$"))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, talk))
    
    # Устанавливаем команды и меню после запуска
    app.post_init = set_bot_commands
    # Запуск бота
    app.run_polling()

if __name__ == '__main__':
    main()