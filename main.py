#!/usr/bin/env python

import logging, os, uuid, json
from telegram import Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

# Получаем токены из переменных окружения
telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
openai_api_key = os.getenv('OPENAI_API_KEY')

# Инициализация клиента OpenAI
client = OpenAI(api_key=openai_api_key)

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
        'Hello and welcome to BookTable.AI!\n'
        'I will help you find the perfect restaurant in Phuket and book a table in seconds.\n\n'
        'Please choose your language or just type a message — I understand more than 120 languages and will reply in yours!',
        reply_markup=reply_markup
    )

    context.user_data['awaiting_language'] = True
    context.user_data['chat_log'] = start_convo.copy()
    context.user_data['sessionid'] = str(uuid.uuid4())
    logger.info("New session with %s", username)

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer(text="", show_alert=False)
    
    # Получаем выбранный язык из callback_data
    lang = query.data.split('_')[1]
    context.user_data['language'] = lang
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
    
    welcome_message = welcome_messages.get(lang, welcome_messages['en'])
    
    # Удаляем сообщение с кнопками
    await query.message.delete()
    
    # Отправляем приветствие на выбранном языке
    await query.message.reply_text(welcome_message)
    
    # Показываем кнопки выбора бюджета
    try:
        # Создаем новый Update для show_budget_buttons
        new_update = Update(update.update_id, message=query.message)
        await show_budget_buttons(new_update, context)
        logger.info("Sent message with keyboard")
    except Exception as e:
        logger.error("Error showing budget buttons: %s", e)
        logger.exception("Full traceback:")
    
    # Инициализируем чат с ChatGPT
    q = "Пользователь выбрал язык. Начни диалог." if lang == 'ru' else "User selected language. Start the conversation."
    try:
        a, chat_log = ask(q, context.user_data['chat_log'])
        context.user_data['chat_log'] = chat_log
    except Exception as e:
        logger.error("Error in ask: %s", e)

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
    context.user_data['budget'] = [budget]
    
    # Показываем сообщение о сохранении
    message = "Запомнил ваш выбор. Его всегда можно изменить. Расскажите, что бы вам хотелось сегодня — я подберу прекрасный вариант и забронирую столик." if context.user_data.get('language') == 'ru' else "I've saved your choice. You can always change it. Tell me what you'd like today — I'll find a perfect option and book a table for you."
    
    # Удаляем кнопки и показываем сообщение
    await query.edit_message_text(message)

async def check_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'budget' in context.user_data:
        budget = context.user_data['budget'][0]
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

    # Обработка выбора бюджета
    if update.message.text in ["$", "$$", "$$$", "$$$$"]:
        budget = str(len(update.message.text))
        if budget in context.user_data['selected_budgets']:
            context.user_data['selected_budgets'].remove(budget)
        else:
            context.user_data['selected_budgets'].add(budget)
        return

    if update.message.text in ["Запомнить", "Save"]:
        if not context.user_data['selected_budgets']:
            await update.message.reply_text(
                "Пожалуйста, выберите хотя бы один ценовой диапазон" if context.user_data.get('language') == 'ru'
                else "Please select at least one price range"
            )
            return
        
        # Сохраняем выбранные бюджеты
        context.user_data['budget'] = sorted(list(context.user_data['selected_budgets']))
        
        # Формируем сообщение о выбранных бюджетах
        budgets_text = ' '.join(['$' * int(b) for b in context.user_data['budget']])
        message = f"Выбранные ценовые диапазоны: {budgets_text}" if context.user_data.get('language') == 'ru' else f"Selected price ranges: {budgets_text}"
        
        # Удаляем кнопки и показываем сообщение о выбранных бюджетах
        await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        return

    try:
        q = update.message.text
        logger.info("%s said: %s", username, q)

        a, chat_log = ask(q, context.user_data['chat_log'])
        context.user_data['chat_log'] = chat_log
        await update.message.reply_text(a)

        logger.info("AI response to %s: %s", username, a)
    except Exception as e:
        logger.error("Error in ask: %s", e)
        if context.user_data.get('language') == 'ru':
            await update.message.reply_text("Извините, произошла ошибка при обработке вашего запроса.")
        else:
            await update.message.reply_text("Sorry, an error occurred while processing your request.")

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