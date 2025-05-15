#!/usr/bin/env python

import logging, os, openai, uuid, configparser, json
from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

# Read config.ini and context.ini
config = configparser.ConfigParser()
config.read('config.ini')
openai.api_key = os.getenv('OPENAI_API_KEY')
telegram_token = config.get('telegram', 'token')

with open('context.json', 'r', encoding='utf-8') as json_file:
    start_convo = json.load(json_file)

def is_this_user_allowed(user_id):
    whitelist = configparser.ConfigParser()
    whitelist.read('users.ini')
    users_str = whitelist.get('whitelist', 'allowed_users')
    users = users_str.split(",")
    if str(user_id) in users:
        return True
    else:
        return False    

def ask(q, chat_log=None):
    if chat_log is None:
        chat_log = start_convo
    chat_log = chat_log + [{"role": "user", "content": q}]
    response = openai.ChatCompletion.create(
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
        chat_log = start_convo
    chat_log = chat_log + [{"role": "user", "content": q}]
    chat_log = chat_log + [{"role": "assistant", "content": a}]
    return chat_log

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user["id"]
    username = user["username"]

    # Временно отключаем проверку авторизации
    # if not is_this_user_allowed(user_id):
    #     await update.message.reply_text(
    #         'Hello and welcome to BookTable.AI!\n'
    #         'I will help you find the perfect restaurant in Phuket and book a table in seconds.\n\n'
    #         'Please choose your language:\n\n'
    #         'Русский\n'
    #         'English\n'
    #         'Français\n'
    #         'العربية\n'
    #         '中文\n'
    #         'ภาษาไทย\n\n'
    #         'Or just type a message — I understand more than 120 languages and will reply in yours!'
    #     )
    #     logger.info("Unauthorized chat request from %s", username)
    #     return

    await update.message.reply_text(
        'Hello and welcome to BookTable.AI!\n'
        'I will help you find the perfect restaurant in Phuket and book a table in seconds.\n\n'
        'Please choose your language:\n\n'
        'Русский\n'
        'English\n'
        'Français\n'
        'العربية\n'
        '中文\n'
        'ภาษาไทย\n\n'
        'Or just type a message — I understand more than 120 languages and will reply in yours!'
    )

    context.user_data['awaiting_language'] = True
    context.user_data['chat_log'] = start_convo
    context.user_data['sessionid'] = str(uuid.uuid4())
    logger.info("New session with %s", username)

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
            await choose_restaurant(update, context)
        else:
            context.user_data['language'] = 'en'
            await choose_restaurant(update, context)
        context.user_data['awaiting_restaurant_choice'] = True
        context.user_data['awaiting_language'] = False
        return

    if context.user_data.get('awaiting_restaurant_choice'):
        text = update.message.text.strip()
        try:
            choice = int(text)
            restaurants = [
                "Ресторан 1",
                "Ресторан 2",
                "Ресторан 3"
            ]
            if 1 <= choice <= len(restaurants):
                selected_restaurant = restaurants[choice - 1]
                if context.user_data.get('language') == 'ru':
                    await update.message.reply_text(f"Вы выбрали: {selected_restaurant}")
                else:
                    await update.message.reply_text(f"You have chosen: {selected_restaurant}")
                context.user_data['awaiting_restaurant_choice'] = False
            else:
                if context.user_data.get('language') == 'ru':
                    await update.message.reply_text("Пожалуйста, выберите корректный номер ресторана.")
                else:
                    await update.message.reply_text("Please select a valid restaurant number.")
        except ValueError:
            if context.user_data.get('language') == 'ru':
                await update.message.reply_text("Пожалуйста, введите номер ресторана.")
            else:
                await update.message.reply_text("Please enter a restaurant number.")
        return

    try:
        dummy = context.user_data['chat_log']
    except:
        logger.warning("chat_log not initialized for user %s", username)
        return

    q = update.message.text
    logger.info("%s said: %s", username, q)

    try:
        a = ask(q, context.user_data['chat_log'])
    except Exception as e:
        logger.error("Error in ask: %s", e)
        if context.user_data.get('language') == 'ru':
            await update.message.reply_text("Извините, произошла ошибка при обработке вашего запроса.")
        else:
            await update.message.reply_text("Sorry, an error occurred while processing your request.")
        return

    context.user_data['chat_log'] = append_interaction_to_chat_log(q, a, context.user_data['chat_log'])
    await update.message.reply_text(a)

    logger.info("AI response to %s: %s", username, a)
    sessionid = context.user_data['sessionid']

async def choose_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    restaurants = [
        "Ресторан 1",
        "Ресторан 2",
        "Ресторан 3"
    ]
    if context.user_data.get('language') == 'ru':
        message = "Пожалуйста, выберите ресторан:\n"
    else:
        message = "Please choose a restaurant:\n"
    for i, restaurant in enumerate(restaurants, start=1):
        message += f"{i}. {restaurant}\n"
    await update.message.reply_text(message)

def main():
    app = ApplicationBuilder().token(telegram_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("choose_restaurant", choose_restaurant))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, talk))
    app.run_polling()

if __name__ == '__main__':
    main()