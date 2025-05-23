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
import requests

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

# Загружаем промпты
with open('prompts.json', 'r', encoding='utf-8') as f:
    PROMPTS = json.load(f)

def get_prompt(task, engine, **kwargs):
    template = PROMPTS.get(task, {}).get(engine, "")
    return template.format(**kwargs)

# --- Быстрая проверка доступности OpenAI ---
def ping_openai():
    try:
        client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.0,
            max_tokens=1
        )
        return True
    except Exception:
        return False

# --- Универсальный слой генерации/диалогов с выбором движка ---
async def ai_generate(task, text=None, target_language=None, preferences=None, context_log=None, context=None):
    """
    Для генерации ответов, рекомендаций, уточнений и т.д. — только OpenAI или ЯндексGPT.
    task: restaurant_recommendation, greet, clarify, fallback_error
    """
    engine = None
    if context and 'ai_engine' in context.user_data:
        engine = context.user_data['ai_engine']
    else:
        # Определяем движок при первом обращении
        if ping_openai():
            engine = 'openai'
        else:
            engine = 'yandex'
        if context:
            context.user_data['ai_engine'] = engine
    if engine == 'openai':
        try:
            if task == 'restaurant_recommendation':
                prompt = get_prompt('restaurant_recommendation', 'openai', preferences=preferences, target_language=target_language)
            elif task == 'greet':
                prompt = get_prompt('greet', 'openai', target_language=target_language)
            elif task == 'clarify':
                prompt = get_prompt('clarify', 'openai', target_language=target_language)
            else:
                prompt = get_prompt('fallback_error', 'openai')
            messages = [{"role": "user", "content": prompt}]
            logger.info(f"[AI] OpenAI prompt: {prompt}")
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            if context:
                context.user_data['ai_engine'] = 'yandex'
            engine = 'yandex'
    if engine == 'yandex':
        try:
            logger.info("[AI] YandexGPT fallback for generation...")
            yandex_api_key = os.getenv('YANDEX_GPT_API_KEY')
            yandex_folder_id = os.getenv('YANDEX_FOLDER_ID')
            if not yandex_api_key or not yandex_folder_id:
                raise Exception('YANDEX_GPT_API_KEY or YANDEX_FOLDER_ID not set')
            if task == 'restaurant_recommendation':
                prompt = get_prompt('restaurant_recommendation', 'yandex', preferences=preferences, target_language=target_language)
            elif task == 'greet':
                prompt = get_prompt('greet', 'yandex', target_language=target_language)
            elif task == 'clarify':
                prompt = get_prompt('clarify', 'yandex', target_language=target_language)
            else:
                prompt = get_prompt('fallback_error', 'yandex')
            url = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
            headers = {
                'Authorization': f'Api-Key {yandex_api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                "modelUri": f"gpt://{yandex_folder_id}/yandexgpt/latest",
                "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 1000},
                "messages": [{"role": "user", "text": prompt}]
            }
            resp = requests.post(url, headers=headers, json=data, timeout=20)
            resp.raise_for_status()
            logger.info(f"[AI] YandexGPT raw response: {resp.text}")
            try:
                result = resp.json()
                text = result['result']['alternatives'][0]['message']['text'].strip()
                return text
            except Exception as parse_e:
                logger.error(f"YandexGPT response parse error: {parse_e}; raw: {resp.text}")
                return get_prompt('fallback_error', 'yandex')
        except Exception as e:
            logger.error(f"YandexGPT error: {e}")
            return get_prompt('fallback_error', 'yandex')
    logger.error(f"All AI engines failed for task {task}")
    return get_prompt('fallback_error', 'yandex')

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
    'location_send': "Please share your current location, I will find a restaurant nearby. Or enter the area as text.",
    'location_thanks': "Thank you! Now I know your location.",
    'area_question': "Choose area:",
    'area_selected': "Great, let's search in the {area} area. What would you like to eat today? I'll find a great option and book a table.",
    'location_any_confirmed': "Okay, I'll search restaurants all over the island.",
    'location_error': "Sorry, I couldn't get your location. Please try again or choose another option.",
    'other_area_prompt': "Please specify the area or location you're interested in.",
    'choose_area_instruction': "Choose an area from the list or type a more precise location",
    'area_not_found_by_coords': "Could not determine the area by coordinates. Please select an area manually.",
    'generic_error': "An error occurred. Please try again.",
    'another_price_not_found': "There are no restaurants in other price categories in this area. Try another area.",
    'area_not_found': "Error: could not determine the area for restaurant search.",
    'search_error': "Error searching for restaurants: {error}",
    'only_restaurant_help': "I can only help with restaurant selection and booking. Tell me what you'd like to eat or which restaurant you're looking for.",
}

# --- Универсальный переводчик: сначала DeepL, потом ai_engine ---
async def translate_message(message_key: str, language: str, **kwargs) -> str:
    """
    Переводит сообщение на нужный язык: сначала DeepL, если не сработал — через выбранный ai_engine (OpenAI или ЯндексGPT).
    """
    base = BASE_MESSAGES[message_key].format(**kwargs)
    logger.info(f"[TRANSLATE] message_key={message_key}, language={language}, base='{base}'")
    if language == 'en':
        logger.info("[TRANSLATE] Язык английский, возврат без перевода.")
        return base
    # 1. DeepL
    try:
        deepl_api_key = os.getenv('DEEPL_API_KEY')
        if deepl_api_key:
            url = 'https://api-free.deepl.com/v2/translate'
            params = {
                'text': base,
                'target_lang': language.upper()
            }
            headers = {
                'Authorization': f'DeepL-Auth-Key {deepl_api_key}'
            }
            logger.info(f"[TRANSLATE] Deepl params: {params}, headers: {headers}")
            resp = requests.post(url, data=params, headers=headers, timeout=20)
            logger.info(f"[TRANSLATE] Deepl response status: {resp.status_code}, text: {resp.text}")
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"[TRANSLATE] Deepl result: {result}")
            return result['translations'][0]['text']
        else:
            logger.warning("[TRANSLATE] DEEPL_API_KEY не найден в окружении!")
    except Exception as e:
        logger.error(f"DeepL error: {e}")
    # 2. ai_engine (OpenAI или Яндекс)
    try:
        context = kwargs.get('context', None)
        engine = None
        if context and 'ai_engine' in context.user_data:
            engine = context.user_data['ai_engine']
        else:
            if ping_openai():
                engine = 'openai'
            else:
                engine = 'yandex'
            if context:
                context.user_data['ai_engine'] = engine
        logger.info(f"[TRANSLATE] Используется AI engine: {engine}")
        if engine == 'openai':
            prompt = get_prompt('translate', 'openai', text=base, target_language=language)
            messages = [{"role": "user", "content": prompt}]
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.3,
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        elif engine == 'yandex':
            yandex_api_key = os.getenv('YANDEX_GPT_API_KEY')
            yandex_folder_id = os.getenv('YANDEX_FOLDER_ID')
            prompt = get_prompt('translate', 'yandex', text=base, target_language=language)
            url = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
            headers = {
                'Authorization': f'Api-Key {yandex_api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                "modelUri": f"gpt://{yandex_folder_id}/yandexgpt/latest",
                "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 1000},
                "messages": [{"role": "user", "text": prompt}]
            }
            resp = requests.post(url, headers=headers, json=data, timeout=20)
            resp.raise_for_status()
            result = resp.json()
            return result['result']['alternatives'][0]['message']['text'].strip()
    except Exception as e:
        logger.error(f"Error translating message: {e}")
    logger.info("[TRANSLATE] Возврат оригинального текста без перевода.")
    return base

# --- Новый универсальный определитель языка ---
def detect_language(text):
    """
    Определяет язык текста через ai_generate (fallback: OpenAI → Yandex).
    Возвращает код языка в формате ISO 639-1.
    """
    try:
        lang = asyncio.run(ai_generate('detect_language', text=text))
        lang = lang.strip().lower()
        # Маппинг для схожих языков
        if lang in ['es', 'ca', 'gl']:
            return 'es'
        elif lang in ['fr', 'oc']:
            return 'fr'
        elif lang in ['ru', 'uk', 'be']:
            return 'ru'
        elif lang in ['zh', 'zh_cn', 'zh_tw']:
            return 'zh'
        elif lang in ['ar', 'fa', 'ur']:
            return 'ar'
        elif lang in ['th', 'lo']:
            return 'th'
        return lang
    except Exception as e:
        logger.error(f"Error detecting language: {e}")
        return 'en'

# --- Новый универсальный генератор ответов ---
async def ask(text, chat_log=None, language='en'):
    """
    Генерирует ответ на сообщение пользователя через ai_generate (fallback: OpenAI → Yandex).
    Возвращает (ответ, обновлённый chat_log).
    """
    try:
        answer = await ai_generate('restaurant_recommendation', text=text, target_language=language, context_log=chat_log)
        # chat_log не обновляем, т.к. ai_generate не ведёт историю
        return answer, chat_log or []
    except Exception as e:
        logger.error(f"Error in ask: {e}")
        return await ai_generate('fallback_error'), chat_log or []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user["id"]
    username = user["username"]

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
    context.user_data['chat_log'] = start_convo.copy()
    context.user_data['sessionid'] = str(uuid.uuid4())
    logger.info("New session with %s", username)

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        lang = query.data.split('_')[1]
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
        welcome_message = await translate_message('welcome', lang)
        # Эффект набора текста перед приветствием
        await context.bot.send_chat_action(chat_id=update.effective_user.id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        if query.message:
            await query.message.reply_text(welcome_message)
        else:
            await context.bot.send_message(chat_id=update.effective_user.id, text=welcome_message)
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
    keyboard = [
        [
            InlineKeyboardButton("$", callback_data="budget_1"),
            InlineKeyboardButton("$$", callback_data="budget_2"),
            InlineKeyboardButton("$$$", callback_data="budget_3"),
            InlineKeyboardButton("$$$$", callback_data="budget_4")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    lang = context.user_data.get('language', 'en')
    message = await translate_message('budget_question', lang)
    # Эффект набора текста перед кнопками бюджета
    chat_id = update.message.chat_id if hasattr(update, 'message') and update.message else update.effective_user.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    if hasattr(update, 'message') and update.message:
        await update.message.reply_text(message, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update.effective_user.id, text=message, reply_markup=reply_markup)

async def budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
    budget = query.data.split('_')[1]
    context.user_data['budget'] = budget
    language = context.user_data.get('language', 'en')
    budget_saved = await translate_message('budget_saved', language)
    await query.message.delete()
    try:
        chat_id = query.message.chat_id
        message_id = query.message.message_id
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id-1)
    except Exception as e:
        logger.error(f"Error deleting previous message: {e}")
    await query.answer()
    await query.message.reply_text(budget_saved)
    context.user_data['awaiting_budget_response'] = True

async def location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    language = context.user_data.get('language', 'en')
    if query.data == 'location_near':
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        keyboard = [[KeyboardButton("📍 Мое местоположение", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        msg = await translate_message('location_send', language)
        await query.message.reply_text(msg, reply_markup=reply_markup)
        context.user_data['awaiting_location_or_area'] = True
        return
    elif query.data == 'location_area':
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
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
        msg = await translate_message('area_question', language)
        await query.message.reply_text(msg, reply_markup=reply_markup)
    elif query.data == 'location_any':
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        context.user_data['location'] = 'any'
        msg = await translate_message('location_any_confirmed', language)
        await query.message.reply_text(msg)
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
    await query.message.delete()
    language = context.user_data.get('language', 'ru')
    area_id = query.data[len('area_'):]  # Исправлено: теперь корректно для phuket_town, bang_tao и других
    if area_id == 'other':
        other_message = await translate_message('other_area_prompt', language)
        await query.message.reply_text(other_message)
        context.user_data['awaiting_area_input'] = True
        return
    area_name = PHUKET_AREAS[area_id]
    context.user_data['location'] = {'area': area_id, 'name': area_name}
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
                    ban_meal_words = "Не используй слова 'завтрак', 'обед', 'ужин', 'бранч' и любые конкретные приёмы пищи. Не используй фразы про отдых, отпуск, путешествие, не делай предположений о статусе пользователя (турист, экспат, резидент). Используй только нейтральные формулировки: 'вашему визиту', 'посещению', 'опыту', 'впечатлениям' и т.д."
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

async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user["id"]
    username = user["username"]
    text = update.message.text.strip()
    detected_lang = detect_language(text)
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
    language = context.user_data.get('language', detected_lang)

    logger.info("Processing message from %s: %s", username, text)

    # --- ДОБАВЛЕНО: обработка ошибочного ввода района для любого текста ---
    restaurant_keywords = ['мясо', 'рыба', 'морепродукты', 'тайская', 'итальянская', 'японская', 
                         'китайская', 'индийская', 'вегетарианская', 'веганская', 'барбекю', 
                         'стейк', 'суши', 'паста', 'пицца', 'бургер', 'фастфуд', 'кафе', 
                         'ресторан', 'кухня', 'еда', 'ужин', 'обед', 'завтрак', 'brunch']
    text_lower = text.lower()
    is_restaurant_related = any(keyword in text_lower for keyword in restaurant_keywords)
    is_command = text_lower.startswith('/')
    # Если это не команда и не про еду ли текст
    if not is_command and not is_restaurant_related and not context.user_data.get('awaiting_location_or_area') and not context.user_data.get('awaiting_area_input'):
        friendly_msg = "Я могу помочь только с выбором ресторана и бронированием. Расскажите, что бы вы хотели поесть или какой ресторан ищете?"
        await update.message.reply_text(friendly_msg)
        return
    # --- КОНЕЦ ДОБАВЛЕНИЯ ---

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
        # Проверяем, не похоже ли на район (старый механизм)
        is_area_like = False
        # Получаем список всех уникальных локаций из базы
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT location FROM restaurants WHERE location IS NOT NULL AND location != ''")
            all_locations = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching locations from DB: {e}")
            all_locations = []
        # Используем OpenAI для сопоставления пользовательского ввода с локациями из базы
        if all_locations:
            prompt = (
                f"Пользователь ввёл: '{text}'. Вот список всех локаций из базы данных: {all_locations}. "
                "Определи, какая локация из базы наиболее соответствует пользовательскому вводу. "
                "Верни только точное значение из списка, без пояснений. Если ничего не подходит, верни 'NO_MATCH'."
            )
            try:
                matched_location = (await ask(prompt, None, detected_lang))[0].strip()
                is_area_like = matched_location != 'NO_MATCH'
            except Exception as e:
                logger.error(f"Error in OpenAI location match: {e}")
                is_area_like = False
        # Логика выбора реакции
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
        elif is_area_like:
            # Сохраняем найденную локацию и ищем рестораны
            context.user_data['location'] = {'area': matched_location, 'name': matched_location}
            await update.message.reply_text(f"Отлично, поищем в районе {matched_location}. Что бы вам хотелось сегодня покушать? Я подберу прекрасный вариант и забронирую столик.")
            await show_pretty_restaurants(update, context)
            return
        else:
            # Не про еду и не район — отдельный промт для болтовни
            try:
                await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
                await asyncio.sleep(1)
                flexible_prompt = f"Пользователь написал: '{text}'. Ответь остроумно, дружелюбно, но мягко верни разговор к выбору ресторана. Не используй шаблонные фразы, не повторяй приветствие. Пиши на языке пользователя ({detected_lang})."
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
        
        a, chat_log = ask(text, context.user_data['chat_log'], detected_lang)
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
    language = context.user_data.get('language', 'en')
    msg = await translate_message('choose_area_instruction', language)
    await query.message.reply_text(msg, reply_markup=reply_markup)

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
                ban_meal_words = "Не используй слова 'завтрак', 'обед', 'ужин', 'бранч' и любые конкретные приёмы пищи. Не используй фразы про отдых, отпуск, путешествие, не делай предположений о статусе пользователя (турист, экспат, резидент). Используй только нейтральные формулировки: 'вашему визиту', 'посещению', 'опыту', 'впечатлениям' и т.д."
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