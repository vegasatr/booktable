#!/usr/bin/env python

import logging, os, uuid, json
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.constants import ChatAction
from dotenv import load_dotenv
from openai import OpenAI
import psycopg2
from psycopg2.extras import DictCursor
from geopy.geocoders import Nominatim
import asyncio
from math import radians, sin, cos, sqrt, atan2

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
        logging.FileHandler("bot.log"),
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

# Список районов Пхукета
PHUKET_AREAS = {
    'chalong': 'Чалонг',
    'festival': 'Фестиваль',
    'patong': 'Паттонг',
    'kata': 'Ката',
    'karon': 'Карон',
    'phuket_town': 'Пхукет-таун',
    'kamala': 'Камала',
    'rawai': 'Равай',
    'nai_harn': 'Най Харн',
    'bang_tao': 'Банг Тао',
    'surin': 'Сурин',
    'other': 'Другой'
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
            'ru': "Я знаю о ресторанах на Пхукете всё.",
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
    
    language = context.user_data.get('language', 'en')
    
    if query.data == 'location_near':
        # Включаем эффект печатания
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)  # Добавляем небольшую задержку
        
        # Проверяем, является ли клиент десктопным
        if update.effective_user.is_bot or not update.effective_user.is_premium:
            await query.message.reply_text(
                "К сожалению, отправка геолокации доступна только в мобильном приложении Telegram. "
                "Пожалуйста, выберите район из списка или укажите любое место на острове."
            )
            # Показываем кнопки районов
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
            return
            
        keyboard = [[KeyboardButton("Отправить мою локацию", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await query.message.reply_text("Пожалуйста, отправьте вашу локацию:", reply_markup=reply_markup)
    
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
    """Обработчик выбора района"""
    query = update.callback_query
    await query.answer()
    
    language = context.user_data.get('language', 'en')
    
    area_id = query.data.split('_')[1]
    
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
    
    # Получаем координаты центра района
    geolocator = Nominatim(user_agent="booktable_bot")
    try:
        location_data = geolocator.geocode(f"{area_name}, Phuket, Thailand")
        if location_data:
            # Сохраняем координаты в базу
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET coordinates = POINT(%s, %s) WHERE telegram_user_id = %s",
                (location_data.longitude, location_data.latitude, update.effective_user.id)
            )
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        logger.error(f"Error getting coordinates for area: {e}")
    
    await query.message.reply_text(f"Выбран район: {area_name}")
    
    # Показываем отладочный список ресторанов
    await debug_show_restaurants(update, context)
    
    # Инициализируем чат с ChatGPT
    q = f"Пользователь выбрал язык, бюджет и район {area_name}. Начни диалог." if language == 'ru' else f"User selected language, budget and area {area_name}. Start the conversation."
    try:
        a, chat_log = ask(q, context.user_data['chat_log'], language)
        context.user_data['chat_log'] = chat_log
        await query.message.reply_text(a)
    except Exception as e:
        logger.error(f"Error in ask: {e}")
        error_message = await translate_message('error', language)
        await query.message.reply_text(error_message)

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Рассчитывает расстояние между двумя точками на Земле в километрах
    используя формулу гаверсинусов
    """
    R = 6371  # радиус Земли в километрах
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return distance

async def debug_show_restaurants(update, context):
    """Отладочная функция для показа подходящих ресторанов"""
    # Получаем критерии
    location = context.user_data.get('location')
    budget = context.user_data.get('budget')
    
    # Преобразуем бюджет в диапазон
    budget_ranges = {
        '1': (0, 500),
        '2': (500, 1500),
        '3': (1500, 3000),
        '4': (3000, 100000)
    }
    min_check, max_check = budget_ranges.get(str(budget), (0, 100000))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        if location == 'any':
            # Если любое место - ищем по всему острову
            cur.execute(
                """SELECT name, average_check, coordinates FROM restaurants
                WHERE average_check >= %s AND average_check <= %s AND active = true
                ORDER BY average_check""", (min_check, max_check)
            )
        elif isinstance(location, dict) and 'area' in location:
            # Если выбран район
            cur.execute(
                """SELECT name, average_check, coordinates FROM restaurants
                WHERE location = %s AND average_check >= %s AND average_check <= %s AND active = true
                ORDER BY average_check""", (location['name'], min_check, max_check)
            )
        elif isinstance(location, dict) and 'lat' in location and 'lon' in location:
            # Если есть точные координаты пользователя
            # Получаем все рестораны в радиусе 5 км
            cur.execute(
                """SELECT name, average_check, coordinates FROM restaurants
                WHERE average_check >= %s AND average_check <= %s AND active = true""",
                (min_check, max_check)
            )
            
            # Фильтруем рестораны по расстоянию
            user_lat = location['lat']
            user_lon = location['lon']
            nearby_restaurants = []
            
            for row in cur.fetchall():
                if row['coordinates']:
                    # Извлекаем координаты из POINT
                    rest_lon, rest_lat = row['coordinates']
                    distance = calculate_distance(user_lat, user_lon, rest_lat, rest_lon)
                    if distance <= 5:  # 5 км радиус
                        nearby_restaurants.append({
                            'name': row['name'],
                            'average_check': row['average_check'],
                            'distance': round(distance, 1)
                        })
            
            # Сортируем по расстоянию
            nearby_restaurants.sort(key=lambda x: x['distance'])
            rows = nearby_restaurants
        else:
            rows = []
            
        if not rows:
            await update.message.reply_text("Нет подходящих ресторанов (отладка)")
        else:
            msg = "Подходящие рестораны (отладка):\n\n"
            for r in rows:
                if isinstance(r, dict) and 'distance' in r:
                    # Если это результат поиска по радиусу
                    msg += f"{r['name']} — {r['average_check']}฿ (в {r['distance']} км)\n"
                else:
                    # Если это результат поиска по району или всему острову
                    msg += f"{r['name']} — {r['average_check']}฿\n"
            await update.message.reply_text(msg)
            
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error in debug_show_restaurants: {e}")
        await update.message.reply_text(f"Ошибка поиска ресторанов: {e}")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик получения геолокации"""
    location = update.message.location
    context.user_data['location'] = {
        'lat': location.latitude,
        'lon': location.longitude
    }
    
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
                "UPDATE users SET coordinates = POINT(%s, %s) WHERE telegram_user_id = %s",
                (location.longitude, location.latitude, update.effective_user.id)
            )
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        logger.error(f"Error getting address from coordinates: {e}")
    
    await update.message.reply_text(
        "Спасибо! Теперь я знаю ваше местоположение.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Показываем отладочный список ресторанов
    await debug_show_restaurants(update, context)
    
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
        
        if not is_restaurant_related:
            # Если ответ не о ресторанах - используем ChatGPT
            try:
                a, chat_log = ask(text, context.user_data['chat_log'], detected_lang)
                context.user_data['chat_log'] = chat_log
                await update.message.reply_text(a)
            except Exception as e:
                logger.error(f"Error in ask: {e}")
                error_message = await translate_message('error', detected_lang)
                await update.message.reply_text(error_message)
        
        # В любом случае показываем кнопки выбора локации в одну строку
        keyboard = [[
            InlineKeyboardButton("РЯДОМ СО МНОЙ", callback_data='location_near'),
            InlineKeyboardButton("ВЫБРАТЬ РАЙОН", callback_data='location_area'),
            InlineKeyboardButton("ЛЮБОЕ МЕСТО", callback_data='location_any')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        location_message = "Прекрасно, подберу для Вас отличный ресторан! Поискать поблизости, в другом районе или в любом месте на Пхукете?"
        await update.message.reply_text(location_message, reply_markup=reply_markup)
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

def main():
    app = ApplicationBuilder().token(telegram_token).build()
    
    # Базовые команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_budget))
    
    # Обработчики callback-запросов
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(budget_callback, pattern="^budget_"))
    app.add_handler(CallbackQueryHandler(location_callback, pattern="^location_"))
    app.add_handler(CallbackQueryHandler(area_callback, pattern="^area_"))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, talk))
    
    # Запуск бота
    app.run_polling()

if __name__ == '__main__':
    main()