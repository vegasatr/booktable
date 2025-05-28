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

# === ЦЕНТРАЛИЗОВАННАЯ СИСТЕМА УПРАВЛЕНИЯ СОСТОЯНИЕМ ===

class UserState:
    """Централизованное управление состоянием пользователя"""
    
    def __init__(self, context):
        self.context = context
        self.user_data = context.user_data
    
    @property
    def language(self):
        return self.user_data.get('language', 'ru')
    
    @property
    def budget(self):
        return self.user_data.get('budget')
    
    @property
    def location(self):
        return self.user_data.get('location')
    
    @property
    def current_screen(self):
        """Текущий экран/состояние пользователя"""
        return self.user_data.get('current_screen', 'start')
    
    def set_budget(self, budget):
        """Устанавливает бюджет и сохраняет в базу"""
        self.user_data['budget'] = budget
        # Сохраняем в базу данных
        user_id = self.context._user_id if hasattr(self.context, '_user_id') else None
        if user_id:
            save_user_preferences(user_id, {'budget': budget})
    
    def set_location(self, location):
        """Устанавливает локацию"""
        self.user_data['location'] = location
    
    def set_screen(self, screen_name):
        """Устанавливает текущий экран"""
        self.user_data['current_screen'] = screen_name
    
    def is_ready_for_restaurants(self):
        """Проверяет, готов ли пользователь для показа ресторанов"""
        return bool(self.budget and self.location)
    
    def get_context_for_return(self):
        """Возвращает контекст для возврата на предыдущий экран"""
        return {
            'screen': self.current_screen,
            'budget': self.budget,
            'location': self.location,
            'language': self.language
        }

class BudgetManager:
    """Централизованное управление бюджетом"""
    
    @staticmethod
    async def show_budget_selection(update, context, return_context=None):
        """Показывает выбор бюджета с возможностью возврата"""
        keyboard = [
            [
                InlineKeyboardButton("$", callback_data="budget_1"),
                InlineKeyboardButton("$$", callback_data="budget_2"),
                InlineKeyboardButton("$$$", callback_data="budget_3"),
                InlineKeyboardButton("$$$$", callback_data="budget_4")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Сохраняем контекст возврата
        if return_context:
            context.user_data['return_context'] = return_context
        
        state = UserState(context)
        message = await translate_message('budget_question', state.language)
        
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)
    
    @staticmethod
    async def handle_budget_change(update, context, new_budget):
        """Обрабатывает смену бюджета и возвращает пользователя в правильное место"""
        query = update.callback_query
        await query.answer()
        await query.message.delete()
        
        logger.info(f"[BUDGET_MANAGER] Starting budget change to: {new_budget}")
        
        # Удаляем приветственное сообщение, если оно есть
        welcome_message_id = context.user_data.get('welcome_message_id')
        if welcome_message_id:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=welcome_message_id)
                logger.info(f"[BUDGET_MANAGER] Deleted welcome message {welcome_message_id}")
                context.user_data.pop('welcome_message_id', None)
            except Exception as e:
                logger.error(f"[BUDGET_MANAGER] Error deleting welcome message {welcome_message_id}: {e}")
        
        state = UserState(context)
        context._user_id = update.effective_user.id  # Сохраняем для UserState
        state.set_budget(new_budget)
        
        logger.info(f"[BUDGET_MANAGER] Budget set to: {new_budget}")
        logger.info(f"[BUDGET_MANAGER] Current state - budget: {state.budget}, location: {state.location}")
        
        # ОБЯЗАТЕЛЬНО показываем сообщение о сохранении выбора с эффектом печатающей машинки
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await asyncio.sleep(0.5)  # Короткий эффект для короткой фразы
        budget_saved_msg = await translate_message('budget_saved', state.language)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=budget_saved_msg)
        
        # Получаем контекст возврата
        return_context = context.user_data.get('return_context')
        logger.info(f"[BUDGET_MANAGER] Return context: {return_context}")
        
        if return_context and return_context.get('screen') == 'restaurant_list':
            # Возвращаемся к списку ресторанов с новым бюджетом
            logger.info("[BUDGET_MANAGER] Returning to restaurant list with new budget")
            await RestaurantDisplay.show_restaurants(update, context)
        elif state.is_ready_for_restaurants():
            # Если есть и бюджет и локация - показываем рестораны
            logger.info("[BUDGET_MANAGER] State ready for restaurants, showing restaurants")
            await RestaurantDisplay.show_restaurants(update, context)
        else:
            # Иначе переходим к выбору локации
            logger.info("[BUDGET_MANAGER] State not ready, showing location selection")
            await LocationManager.show_location_selection(update, context)

class RestaurantDisplay:
    """Централизованное отображение ресторанов"""
    
    @staticmethod
    async def show_restaurants(update, context):
        """Показывает рестораны на основе текущего состояния"""
        logger.info("[RESTAURANT_DISPLAY] Starting show_restaurants")
        
        state = UserState(context)
        state.set_screen('restaurant_list')
        
        logger.info(f"[RESTAURANT_DISPLAY] State: budget={state.budget}, location={state.location}")
        
        # Удаляем предыдущие сообщения с предложением изменить бюджет, если они есть
        previous_message_ids = context.user_data.get('budget_change_message_ids', [])
        for msg_id in previous_message_ids:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                logger.info(f"[RESTAURANT_DISPLAY] Deleted previous message {msg_id}")
            except Exception as e:
                logger.error(f"[RESTAURANT_DISPLAY] Error deleting message {msg_id}: {e}")
        # Очищаем список ID сообщений
        context.user_data['budget_change_message_ids'] = []
        
        logger.info("[RESTAURANT_DISPLAY] Calling show_pretty_restaurants")
        # Вызываем существующую функцию
        await show_pretty_restaurants(update, context)
    
    @staticmethod
    async def _clear_previous_messages(update, context):
        """Удаляет предыдущие сообщения"""
        previous_message_ids = context.user_data.get('budget_change_message_ids', [])
        for msg_id in previous_message_ids:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except Exception as e:
                logger.error(f"Error deleting message {msg_id}: {e}")
        context.user_data['budget_change_message_ids'] = []

class LocationManager:
    """Управление выбором локации"""
    
    @staticmethod
    async def show_location_selection(update, context):
        """Показывает выбор локации"""
        keyboard = [[
            InlineKeyboardButton("РЯДОМ", callback_data='location_near'),
            InlineKeyboardButton("РАЙОН", callback_data='location_area'),
            InlineKeyboardButton("ВЕЗДЕ", callback_data='location_any')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        state = UserState(context)
        message = "Подберу для Вас отличный ресторан! Поискать поблизости, в другом районе или в любом месте на Пхукете?"
        
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)

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
openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o')

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
            model=openai_model,
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
    task: restaurant_recommendation, greet, clarify, fallback_error, restaurant_qa
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
            elif task == 'restaurant_qa':
                prompt = get_prompt('restaurant_qa', 'openai', text=text)
            else:
                prompt = get_prompt('fallback_error', 'openai')
            messages = [{"role": "user", "content": prompt}]
            logger.info(f"[AI] OpenAI prompt: {prompt}")
            response = client.chat.completions.create(
                model=openai_model,
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
            if task == 'restaurant_recommendation':
                prompt = get_prompt('restaurant_recommendation', 'yandex', preferences=preferences, target_language=target_language)
            elif task == 'greet':
                prompt = get_prompt('greet', 'yandex', target_language=target_language)
            elif task == 'clarify':
                prompt = get_prompt('clarify', 'yandex', target_language=target_language)
            elif task == 'restaurant_qa':
                prompt = get_prompt('restaurant_qa', 'yandex', text=text)
            else:
                prompt = get_prompt('fallback_error', 'yandex')
            url = 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion'
            headers = {
                'Authorization': f'Api-Key {os.getenv("YANDEX_GPT_API_KEY")}',
                'Content-Type': 'application/json'
            }
            data = {
                "modelUri": f"gpt://{os.getenv('YANDEX_FOLDER_ID')}/yandexgpt/latest",
                "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 1000},
                "messages": [{"role": "user", "text": prompt}]
            }
            resp = requests.post(url, headers=headers, json=data, timeout=20)
            resp.raise_for_status()
            logger.info(f"[AI] YandexGPT raw response: {resp.text}")
            try:
                result = resp.json()
                text = result['result']['alternatives'][0]['message']['text'].strip()
                logger.debug(f"[TRANSLATE] DeepL response JSON: {result}")
                logger.debug(f"[TRANSLATE] Translated text: {result['translations'][0]['text']}")
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
    'patong': 'Патонг',
    'kata': 'Ката',
    'karon': 'Карон',
    'phuket_town': 'Пхукет-таун',
    'kamala': 'Камала',
    'rawai': 'Равай',
    'nai_harn': 'Най Харн',
    'bang_tao': 'Банг Тао',
    'other': 'Другой'
}

# Сопоставление ключей районов с их названиями в базе данных
AREA_DB_MAPPING = {
    'chalong': 'Chalong',
    'patong': 'Patong',
    'kata': 'Kata',
    'karon': 'Karon',
    'phuket_town': 'Phuket Town',
    'kamala': 'Kamala',
    'rawai': 'Rawai',
    'nai_harn': 'Nai Harn',
    'bang_tao': 'Bang Tao'
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
with open('messages/base_messages.txt', 'r', encoding='utf-8') as f:
    BASE_MESSAGES = json.load(f)

# --- Новый универсальный определитель языка ---
async def detect_language(text):
    """
    Определяет язык текста через ai_generate (fallback: OpenAI → Yandex).
    Возвращает код языка в формате ISO 639-1.
    """
    try:
        lang = await ai_generate('detect_language', text=text)
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
    context.user_data['chat_log'] = []  # Исправлено: убрал неопределенную переменную start_convo
    context.user_data['sessionid'] = str(uuid.uuid4())
    logger.info("New session with %s", username)

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        welcome_message = await translate_message('welcome', lang)
        # Эффект набора текста перед приветствием
        await context.bot.send_chat_action(chat_id=update.effective_user.id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
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
    """Показывает кнопки выбора бюджета - теперь использует BudgetManager"""
    await BudgetManager.show_budget_selection(update, context)

async def budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора бюджета - теперь использует централизованную архитектуру"""
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
    
    await BudgetManager.handle_budget_change(update, context, budget)
    
    # Обновляем команды меню после выбора бюджета
    await context.bot.set_my_commands([
        ("restart", "Перезапустить бота"),
        ("new_search", "Новый поиск")
    ])

async def translate_message(message_key, language, **kwargs):
    """
    Переводит базовое сообщение на указанный язык.
    Если язык английский или перевод не удался, возвращает оригинальный текст.
    """
    logger.info(f"[TRANSLATE] message_key={message_key}, language={language}")
    base = BASE_MESSAGES.get(message_key, '')
    if not base:
        logger.error(f"[TRANSLATE] Сообщение не найдено: {message_key}")
        return message_key
        
    if kwargs:
        try:
            base = base.format(**kwargs)
        except KeyError as e:
            logger.error(f"[TRANSLATE] Ошибка форматирования: {e}")
            return base
            
    if language == 'en':
        logger.info("[TRANSLATE] Язык английский, возврат без перевода.")
        return base
    try:
        # Более специфичный запрос на перевод, который гарантирует точный перевод базового сообщения
        prompt = f"Translate this exact text to {language}. Return ONLY the translation, no explanations or additional text: {base}"
        messages = [{"role": "user", "content": prompt}]
        response = client.chat.completions.create(
            model=openai_model,
            messages=messages,
            temperature=0.3,
            max_tokens=100
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"[TRANSLATE] Успешный перевод: {translated}")
        return translated
    except Exception as e:
        logger.error(f"[TRANSLATE] Ошибка перевода: {e}")
    logger.info("[TRANSLATE] Возврат оригинального текста без перевода.")
    return base

async def location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    
    # Получаем язык из context.user_data или из базы данных
    language = context.user_data.get('language')
    if not language:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            cur.execute("SELECT language FROM users WHERE telegram_user_id = %s", (update.effective_user.id,))
            result = cur.fetchone()
            if result:
                language = result['language']
                context.user_data['language'] = language
            else:
                language = 'en'  # Fallback to English if no language found
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error getting language from DB: {e}")
            language = 'en'  # Fallback to English on error
    
    logger.info(f"[LOCATION] language={language}")
    
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
        msg = await translate_message('choose_area_instruction', language)
        logger.info(f"[LOCATION] choose_area_instruction translated: {msg}")
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
            await query.message.reply_text(a)
        except Exception as e:
            logger.error(f"Error in ask: {e}")
            error_message = await translate_message('error', language)
            await query.message.reply_text(error_message)

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

# --- Новая функция для перевода текста через AI ---
async def translate_text(text: str, target_language: str) -> str:
    """
    Простая функция для перевода текста через AI.
    Использует OpenAI для перевода, возвращает оригинальный текст в случае ошибки.
    """
    try:
        prompt = f"Translate this text to {target_language}. Return ONLY the translation, no explanations: {text}"
        messages = [{"role": "user", "content": prompt}]
        response = client.chat.completions.create(
            model=openai_model,
            messages=messages,
            temperature=0.3,
            max_tokens=100
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"[TRANSLATE_TEXT] Translated '{text}' to '{translated}'")
        return translated
    except Exception as e:
        logger.error(f"[TRANSLATE_TEXT] Error translating text: {e}")
        return text

# Новая функция для красивого вывода ресторанов
async def show_pretty_restaurants(update, context):
    """Показывает красиво оформленный список подходящих ресторанов"""
    location = context.user_data.get('location')
    budget = context.user_data.get('budget')
    language = context.user_data.get('language', 'ru')

    logger.info(f"[SHOW_RESTAURANTS] Starting with location={location}, budget={budget} (type: {type(budget)}), language={language}")

    # Удаляем предыдущие сообщения с предложением изменить бюджет, если они есть
    previous_message_ids = context.user_data.get('budget_change_message_ids', [])
    for msg_id in previous_message_ids:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            logger.info(f"[SHOW_RESTAURANTS] Deleted previous message {msg_id}")
        except Exception as e:
            logger.error(f"[SHOW_RESTAURANTS] Error deleting message {msg_id}: {e}")
    # Очищаем список ID сообщений
    context.user_data['budget_change_message_ids'] = []

    # Бюджет уже приходит в правильном формате ($, $$, $$$, $$$$)
    budget_str = budget
    logger.info(f"[SHOW_RESTAURANTS] Using budget_str={budget_str} directly from budget={budget}")

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)

        if isinstance(location, dict) and 'area' in location:
            area_key = location['area']
            # Получаем правильное название района для поиска в базе данных
            db_area_name = AREA_DB_MAPPING.get(area_key, location.get('name', ''))
            
            logger.info(f"[SHOW_RESTAURANTS] Area key: {area_key}, DB area name: {db_area_name}")
            
            # Сначала проверяем, есть ли рестораны в этом районе вообще
            cur.execute("""
                SELECT DISTINCT average_check::text as budget
                FROM restaurants 
                WHERE LOWER(location) ILIKE %s
                AND active ILIKE 'true'
                ORDER BY average_check::text
            """, (f"%{db_area_name.lower()}%",))
            
            available_budgets = [row['budget'] for row in cur.fetchall()]
            logger.info(f"[SHOW_RESTAURANTS] Available budgets in area: {available_budgets}")

            if not available_budgets:
                # Если нет ресторанов с выбранным бюджетом, показываем сообщение и кнопки с доступными бюджетами
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(1)
                
                # Создаем кнопки для доступных бюджетов
                keyboard = []
                row = []
                
                # Маппинг для конвертации символов доллара в числа для callback_data
                dollar_to_number = {
                    '$': '1',
                    '$$': '2', 
                    '$$$': '3',
                    '$$$$': '4'
                }
                
                for budget in available_budgets:
                    budget_label = budget  # Показываем символы доллара как есть
                    budget_number = dollar_to_number.get(budget, budget)
                    row.append(InlineKeyboardButton(budget_label, callback_data=f'budget_{budget_number}'))
                    if len(row) == 3:  # Максимум 3 кнопки бюджета в строке
                        keyboard.append(row)
                        row = []
                if row:  # Добавляем оставшиеся кнопки бюджета
                    keyboard.append(row)
                
                # Добавляем кнопку изменения района в последнюю строку
                if keyboard:
                    keyboard[-1].append(InlineKeyboardButton("РАЙОН", callback_data='choose_area'))
                else:
                    keyboard.append([InlineKeyboardButton("РАЙОН", callback_data='choose_area')])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Сохраняем контекст возврата для кнопок бюджета
                state = UserState(context)
                context.user_data['return_context'] = {
                    'screen': 'restaurant_list',
                    'budget': state.budget,
                    'location': state.location,
                    'language': state.language
                }
                
                # Объединяем два сообщения в одно
                combined_msg = await translate_message('no_restaurants_in_budget', language, budget=budget_str)
                sent_message = await update.effective_chat.send_message(combined_msg, reply_markup=reply_markup)
                
                # Сохраняем ID сообщения для последующего удаления
                if 'budget_change_message_ids' not in context.user_data:
                    context.user_data['budget_change_message_ids'] = []
                context.user_data['budget_change_message_ids'].append(sent_message.message_id)
                
                cur.close()
                conn.close()
                return

            # Теперь ищем рестораны с выбранным бюджетом
            query = """
                SELECT r.name, r.average_check, r.location, r.cuisine, r.features
                FROM restaurants r
                WHERE LOWER(r.location) ILIKE %s
                AND r.average_check::text = %s AND r.active ILIKE 'true'
                ORDER BY r.name
            """
            params = (f"%{db_area_name.lower()}%", budget_str)

            logger.info(f"[SHOW_RESTAURANTS] Executing query: {query}")
            logger.info(f"[SHOW_RESTAURANTS] With params: {params}")
            
            cur.execute(query, params)
            rows = cur.fetchall()
            logger.info(f"[SHOW_RESTAURANTS] Found {len(rows)} restaurants")
            
            if not rows:
                # Если нет ресторанов с выбранным бюджетом, показываем сообщение и кнопки с доступными бюджетами
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(1)
                
                # Создаем кнопки для доступных бюджетов
                keyboard = []
                row = []
                
                # Маппинг для конвертации символов доллара в числа для callback_data
                dollar_to_number = {
                    '$': '1',
                    '$$': '2', 
                    '$$$': '3',
                    '$$$$': '4'
                }
                
                for budget in available_budgets:
                    budget_label = budget  # Показываем символы доллара как есть
                    budget_number = dollar_to_number.get(budget, budget)
                    row.append(InlineKeyboardButton(budget_label, callback_data=f'budget_{budget_number}'))
                    if len(row) == 3:  # Максимум 3 кнопки бюджета в строке
                        keyboard.append(row)
                        row = []
                if row:  # Добавляем оставшиеся кнопки бюджета
                    keyboard.append(row)
                
                # Добавляем кнопку изменения района в последнюю строку
                if keyboard:
                    keyboard[-1].append(InlineKeyboardButton("РАЙОН", callback_data='choose_area'))
                else:
                    keyboard.append([InlineKeyboardButton("РАЙОН", callback_data='choose_area')])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Сохраняем контекст возврата для кнопок бюджета
                state = UserState(context)
                context.user_data['return_context'] = {
                    'screen': 'restaurant_list',
                    'budget': state.budget,
                    'location': state.location,
                    'language': state.language
                }
                
                # Объединяем два сообщения в одно
                combined_msg = await translate_message("no_restaurants_in_budget", language, budget=budget_str)
                sent_message = await update.effective_chat.send_message(combined_msg, reply_markup=reply_markup)
                
                # Сохраняем ID сообщения для последующего удаления
                if 'budget_change_message_ids' not in context.user_data:
                    context.user_data['budget_change_message_ids'] = []
                context.user_data['budget_change_message_ids'].append(sent_message.message_id)
                
                cur.close()
                conn.close()
                return

            # Отправляем сообщение с рекомендацией
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            await asyncio.sleep(1)
            recommendation_msg = await translate_message('restaurant_recommendation', language)
            await update.effective_chat.send_message(recommendation_msg)

            # Формируем и отправляем информацию о каждом ресторане
            for r in rows:
                logger.info(f"[SHOW_RESTAURANTS] Processing restaurant: {r['name']}")
                logger.info(f"[SHOW_RESTAURANTS] Raw data from DB: {dict(r)}")
                
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(1)
                
                msg = f"• {r['name']}\n"
                # Переводим кухню
                if r['cuisine']:
                    translated_cuisine = await translate_text(r['cuisine'], language)
                    msg += f"{translated_cuisine}\n"
                msg += f"{r['average_check']}\n"
                # Переводим особенности
                if r['features']:
                    features_text = r['features']
                    if isinstance(features_text, list):
                        features_text = ', '.join(features_text)
                    translated_features = await translate_text(features_text, language)
                    msg += f"{translated_features}\n"
                logger.info(f"[SHOW_RESTAURANTS] Final message to send: {msg}")
                await update.effective_chat.send_message(msg)

            # Сохраняем информацию о ресторанах для последующего использования
            context.user_data['filtered_restaurants'] = [dict(r) for r in rows]
            logger.info(f"[SHOW_RESTAURANTS] Saved {len(rows)} restaurants to context")

            # Создаем кнопки действий
            keyboard = [
                [
                    InlineKeyboardButton("БРОНИРУЮ", callback_data="book_restaurant"),
                    InlineKeyboardButton("ЕСТЬ ВОПРОС", callback_data="ask_about_restaurant"),
                    InlineKeyboardButton("ДРУГОЙ РАЙОН", callback_data="choose_area")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            logger.info("[SHOW_RESTAURANTS] Created keyboard with buttons")

            # Устанавливаем режим консультации
            context.user_data['consultation_mode'] = True
            context.user_data['restaurant_info'] = "\n".join([
                f"Restaurant: {r['name']}\nCuisine: {r['cuisine']}\nFeatures: {r['features']}" for r in rows
            ])

            # Отправляем приветственное сообщение
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            await asyncio.sleep(1)
            welcome_msg = await translate_message('consultation_welcome', language)
            logger.info(f"[SHOW_RESTAURANTS] Sending welcome message with keyboard: {welcome_msg}")
            await update.effective_chat.send_message(welcome_msg, reply_markup=reply_markup)
            logger.info("[SHOW_RESTAURANTS] Welcome message sent with keyboard")

        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"[SHOW_RESTAURANTS] Error: {e}")
        logger.exception("[SHOW_RESTAURANTS] Full traceback:")
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

async def ask_about_restaurant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("[ASK_ABOUT_RESTAURANT] Callback triggered")
    query = update.callback_query
    logger.info(f"[ASK_ABOUT_RESTAURANT] Query data: {query.data}")
    
    try:
        await query.answer()
        logger.info("[ASK_ABOUT_RESTAURANT] Query answered")
        
        await query.message.delete()
        logger.info("[ASK_ABOUT_RESTAURANT] Message deleted")
        
        # Получаем информацию о ресторанах
        restaurants = context.user_data.get('filtered_restaurants', [])
        logger.info(f"[ASK_ABOUT_RESTAURANT] Found {len(restaurants)} restaurants in context")
        logger.info(f"[ASK_ABOUT_RESTAURANT] Raw restaurant data: {restaurants}")
        
        if not restaurants:
            logger.warning("[ASK_ABOUT_RESTAURANT] No restaurants found in context")
            await update.effective_chat.send_message("Извините, информация о ресторанах недоступна. Пожалуйста, начните поиск заново.")
            return

        # Получаем предпочтения пользователя
        user_wish = context.user_data.get('last_user_wish', '')
        language = context.user_data.get('language', 'ru')
        logger.info(f"[ASK_ABOUT_RESTAURANT] User wish: {user_wish}, language: {language}")

        # Формируем контекст для ChatGPT
        restaurant_info = []
        for r in restaurants:
            info = {
                'name': r.get('name', ''),
                'cuisine': r.get('cuisine', ''),
                'average_check': r.get('average_check', ''),
                'features': r.get('features', ''),
                'atmosphere': r.get('atmosphere', ''),
                'story_or_concept': r.get('story_or_concept', '')
            }
            restaurant_info.append(info)
            logger.info(f"[ASK_ABOUT_RESTAURANT] Processed restaurant info: {info}")

        # Преобразуем в строку для промпта
        restaurant_info_str = "\n".join([
            f"Restaurant: {r['name']}\n"
            f"Cuisine: {r['cuisine']}\n"
            f"Average check: {r['average_check']}\n"
            f"Features: {r['features']}\n"
            f"Atmosphere: {r['atmosphere']}\n"
            f"Story: {r['story_or_concept']}\n"
            for r in restaurant_info
        ])
        logger.info(f"[ASK_ABOUT_RESTAURANT] Formatted restaurant info: {restaurant_info_str}")

        # Устанавливаем флаг, что мы в режиме консультации
        context.user_data['consultation_mode'] = True
        context.user_data['restaurant_info'] = restaurant_info_str
        context.user_data['in_restaurant_qa'] = True
        logger.info("[ASK_ABOUT_RESTAURANT] Context flags set")

        # Отправляем простое приветственное сообщение
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        welcome_msg = await translate_message('ready_to_answer', language)
        logger.info(f"[ASK_ABOUT_RESTAURANT] Sending welcome message: {welcome_msg}")
        await update.effective_chat.send_message(welcome_msg)
        logger.info("[ASK_ABOUT_RESTAURANT] Welcome message sent")
        
    except Exception as e:
        logger.error(f"[ASK_ABOUT_RESTAURANT] Error: {e}")
        logger.exception("[ASK_ABOUT_RESTAURANT] Full traceback:")
        try:
            await update.effective_chat.send_message("Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        except Exception as send_e:
            logger.error(f"[ASK_ABOUT_RESTAURANT] Failed to send error message: {send_e}")

async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user["id"]
    username = user["username"]
    text = update.message.text.strip()
    
    # Проверяем состояние пользователя
    state = UserState(context)
    
    # Если пользователь еще не выбрал бюджет, игнорируем сообщение
    if not state.budget:
        logger.info(f"[TALK] User {username} sent message without budget selected, ignoring")
        return
    
    detected_lang = await detect_language(text)
    
    # Получаем текущий язык из базы данных
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT language FROM users WHERE telegram_user_id = %s", (user.id,))
        result = cur.fetchone()
        if result:
            language = result['language']
            context.user_data['language'] = language
        else:
            language = detected_lang
            context.user_data['language'] = language
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error getting language from DB: {e}")
        language = detected_lang
        context.user_data['language'] = language

    logger.info("Processing message from %s: %s", username, text)

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
        
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        welcome_message = await translate_message('welcome', detected_lang)
        await update.message.reply_text(welcome_message)
        
        await show_budget_buttons(update, context)
        return

    # Если это ответ после выбора бюджета
    if context.user_data.get('awaiting_budget_response'):
        context.user_data['awaiting_budget_response'] = False
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        context.user_data['last_user_wish'] = text

        keyboard = [[
            InlineKeyboardButton("РЯДОМ", callback_data='location_near'),
            InlineKeyboardButton("РАЙОН", callback_data='location_area'),
            InlineKeyboardButton("ВЕЗДЕ", callback_data='location_any')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        location_message = "Подберу для Вас отличный ресторан! Поискать поблизости, в другом районе или в любом месте на Пхукете?"
        await update.message.reply_text(location_message, reply_markup=reply_markup)
        return

    # Если есть отфильтрованные рестораны, обрабатываем вопрос как нажатие на кнопку "ЕСТЬ ВОПРОС"
    if context.user_data.get('filtered_restaurants'):
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        restaurants = context.user_data.get('filtered_restaurants', [])
        restaurant_info = context.user_data.get('restaurant_info', '')
        
        # Проверяем, хочет ли пользователь сменить район
        if any(word in text.lower() for word in ['другой район', 'сменить район', 'не подходит', 'не нравится', 'не хочу']):
            context.user_data['in_restaurant_qa'] = False
            keyboard = [[
                InlineKeyboardButton("РЯДОМ", callback_data='location_near'),
                InlineKeyboardButton("РАЙОН", callback_data='location_area'),
                InlineKeyboardButton("ВЕЗДЕ", callback_data='location_any')
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Хорошо, давайте подберем ресторан в другом районе!", reply_markup=reply_markup)
            return

        # Формируем промпт для AI с учетом контекста
        prompt = f"""
        Ты - опытный консультант по ресторанам на Пхукете. Ты знаешь все о ресторанах на острове - от отзывов на TripAdvisor до информации с сайтов ресторанов и Google Maps. Ты работаешь в этом бизнесе много лет и действительно ЗНАЕШЬ все о ресторанах.

        Вопрос клиента: '{text}'

        Информация о ресторанах из базы данных:
        {restaurant_info}

        Структура данных о ресторане:
        - name: название ресторана
        - cuisine: тип кухни
        - average_check: средний чек
        - location: расположение
        - features: особенности (список)
        - atmosphere: атмосфера
        - story_or_concept: история или концепция
        - menu_items: блюда в меню (список)
        - special_dishes: специальные блюда (список)
        - wine_selection: винная карта
        - opening_hours: часы работы
        - contact_info: контактная информация

        Правила ответов:
        1. Всегда отвечай на основе данных из базы и своих знаний о ресторане
        2. Отвечай на языке клиента ({language})
        3. Будь дружелюбным и естественным
        4. Отвечай от первого лица
        5. Давай конкретные ответы на конкретные вопросы
        6. Используй контекст предыдущих вопросов
        7. Если клиент спрашивает "какие" после вопроса о наличии чего-то - перечисли 2-3 конкретных блюда
        8. Если информации нет в базе - используй свои знания о ресторане
        9. Если нужно больше информации - вежливо попроси уточнить

        Строго запрещено:
        1. Упоминать базу данных, AI, бота или технические детали
        2. Использовать формальные фразы
        3. Выдумывать информацию
        4. Просить уточнить вопрос, если контекст понятен
        5. Говорить, что вопрос неполный или непонятный
        6. Использовать фразы типа "Извините" или "Пожалуйста"
        7. Давать общие рассуждения вместо конкретики
        8. Перечислять все особенности ресторана, если спрашивают про что-то конкретное
        9. Использовать шаблонные фразы
        10. Отвечать на вопрос, который не задавали

        Верни только ответ на вопрос, без дополнительных пояснений.
        """
        
        try:
            # Логируем промпт
            logger.info(f"[RESTAURANT_QA] Sending prompt to AI: {prompt}")
            
            # Определяем язык ответа и используем правильный task
            response = await ai_generate('restaurant_qa', text=prompt, target_language=language)
            
            # Логируем ответ
            logger.info(f"[RESTAURANT_QA] Received response from AI: {response}")
            
            # Отправляем ответ пользователю
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in restaurant QA: {e}")
            error_message = await translate_message('error', language)
            await update.message.reply_text(error_message)
        return

    # Обычный диалог
    try:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        a, chat_log = ask(text, context.user_data['chat_log'], language)
        context.user_data['chat_log'] = chat_log
        await update.message.reply_text(a)
    except Exception as e:
        logger.error("Error in ask: %s", e)
        error_message = await translate_message('error', language)
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
    keyboard = [[
        InlineKeyboardButton("РЯДОМ", callback_data='location_near'),
        InlineKeyboardButton("РАЙОН", callback_data='location_area'),
        InlineKeyboardButton("ВЕЗДЕ", callback_data='location_any')
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Эффект набора текста
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    
    await update.message.reply_text(
        "Подберу для Вас отличный ресторан! Поискать поблизости, в другом районе или в любом месте на Пхукете?",
        reply_markup=reply_markup
    )

async def set_bot_commands(app):
    """Устанавливает команды бота в меню"""
    commands = [
        ("restart", "Перезапустить бота"),
        ("new_search", "Новый поиск")
    ]
    
    # Всегда устанавливаем команды меню
    await app.bot.set_my_commands(commands)
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

# Добавляем новые обработчики для кнопок
async def book_restaurant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    # TODO: Реализовать логику бронирования
    await update.effective_chat.send_message("Функция бронирования будет доступна в следующем обновлении.")

def save_user_preferences(user_id, preferences):
    """Сохраняет предпочтения пользователя в базу данных"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Обновляем предпочтения пользователя
        update_query = """
            UPDATE users 
            SET budget = %s,
                last_search_area = %s,
                last_search_location = %s,
                preferences_updated_at = CURRENT_TIMESTAMP
            WHERE telegram_user_id = %s
        """
        cur.execute(update_query, (
            preferences.get('budget'),
            preferences.get('area'),
            preferences.get('location'),
            user_id
        ))
        
        conn.commit()
        logger.info(f"[DB] Saved preferences for user {user_id}: {preferences}")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"[DB] Error saving preferences: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def get_user_preferences(user_id):
    """Получает предпочтения пользователя из базы данных"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Получаем предпочтения пользователя
        select_query = """
            SELECT budget, last_search_area, last_search_location
            FROM users
            WHERE telegram_user_id = %s
        """
        cur.execute(select_query, (user_id,))
        result = cur.fetchone()
        
        if result:
            preferences = {
                'budget': result['budget'],
                'area': result['last_search_area'],
                'location': result['last_search_location']
            }
            logger.info(f"[DB] Retrieved preferences for user {user_id}: {preferences}")
            return preferences
        return None
    except Exception as e:
        logger.error(f"[DB] Error getting preferences: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Добавляем обработчик для кнопки "ЧЕК"
async def change_budget_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик для кнопки изменения бюджета - теперь использует BudgetManager"""
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
    await BudgetManager.show_budget_selection(update, context, return_context)

def main():
    app = ApplicationBuilder().token(telegram_token).build()
    
    # Базовые команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("filter", check_budget))
    app.add_handler(CommandHandler("new_search", new_search))  # Добавляем новый обработчик
    
    # Обработчики callback-запросов
    app.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(budget_callback, pattern="^budget_"))
    app.add_handler(CallbackQueryHandler(location_callback, pattern="^location_"))
    app.add_handler(CallbackQueryHandler(area_callback, pattern="^area_"))
    app.add_handler(CallbackQueryHandler(choose_area_callback, pattern="^choose_area$"))
    app.add_handler(CallbackQueryHandler(change_budget_callback, pattern="^change_budget$"))
    app.add_handler(CallbackQueryHandler(show_other_price_callback, pattern="^show_other_price$"))
    app.add_handler(CallbackQueryHandler(book_restaurant_callback, pattern="^book_restaurant$"))
    app.add_handler(CallbackQueryHandler(ask_about_restaurant_callback, pattern="^ask_about_restaurant$"))
    
    # Обработчики сообщений
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, talk))
    
    # Устанавливаем команды и меню после запуска
    app.post_init = set_bot_commands
    # Запуск бота
    app.run_polling()

if __name__ == '__main__':
    main()