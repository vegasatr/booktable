"""
Модуль для отображения ресторанов
"""
import logging
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction

from ..database.restaurants import get_restaurants_by_area, get_available_budgets_in_area, get_restaurants_by_location_any
from ..ai.translation import translate_message, translate_text
from .user_state import UserState

logger = logging.getLogger(__name__)

async def show_restaurants(update, context):
    """Показывает рестораны на основе текущего состояния"""
    logger.info("[RESTAURANT_DISPLAY] Starting show_restaurants")
    
    state = UserState(context)
    location = state.location
    budget = state.budget
    language = state.language
    
    logger.info(f"[RESTAURANT_DISPLAY] State: budget={budget}, location={location}")
    
    # Удаляем предыдущие сообщения с предложением изменить бюджет, если они есть
    await _clear_previous_budget_messages(update, context)
    
    if isinstance(location, dict) and 'area' in location:
        await _show_restaurants_by_area(update, context, location, budget, language)
    elif location == 'any':
        await _show_restaurants_any_location(update, context, budget, language)
    else:
        logger.error(f"[RESTAURANT_DISPLAY] Unknown location type: {location}")
        await update.effective_chat.send_message("Ошибка: неизвестный тип локации")

async def _clear_previous_budget_messages(update, context):
    """Удаляет предыдущие сообщения с предложением изменить бюджет"""
    previous_message_ids = context.user_data.get('budget_change_message_ids', [])
    for msg_id in previous_message_ids:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            logger.info(f"[RESTAURANT_DISPLAY] Deleted previous message {msg_id}")
        except Exception as e:
            logger.error(f"[RESTAURANT_DISPLAY] Error deleting message {msg_id}: {e}")
    # Очищаем список ID сообщений
    context.user_data['budget_change_message_ids'] = []

async def _show_restaurants_by_area(update, context, location, budget, language):
    """Показывает рестораны в конкретном районе"""
    area_key = location['area']
    
    # Получаем доступные бюджеты в районе
    available_budgets = await get_available_budgets_in_area(area_key)
    
    if not available_budgets:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        await update.effective_chat.send_message("В этом районе нет активных ресторанов.")
        return
    
    # Получаем рестораны с выбранным бюджетом
    restaurants = await get_restaurants_by_area(area_key, budget)
    
    if not restaurants:
        await _show_budget_options(update, context, available_budgets, budget, language)
        return
    
    await _display_restaurants_list(update, context, restaurants, language)

async def _show_restaurants_any_location(update, context, budget, language):
    """Показывает рестораны по всему острову"""
    restaurants = await get_restaurants_by_location_any(budget)
    
    if not restaurants:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        await update.effective_chat.send_message("Нет ресторанов с выбранным бюджетом.")
        return
    
    await _display_restaurants_list(update, context, restaurants, language)

async def _show_budget_options(update, context, available_budgets, current_budget, language):
    """Показывает опции смены бюджета"""
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
        keyboard[-1].append(InlineKeyboardButton("РАЙОН", callback_data='location_area'))
    else:
        keyboard.append([InlineKeyboardButton("РАЙОН", callback_data='location_area')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Сохраняем контекст возврата для кнопок бюджета
    state = UserState(context)
    context.user_data['return_context'] = {
        'screen': 'restaurant_list',
        'budget': state.budget,
        'location': state.location,
        'language': state.language
    }
    
    # Отправляем сообщение с опциями бюджета
    combined_msg = await translate_message('no_restaurants_in_budget', language, budget=current_budget)
    sent_message = await update.effective_chat.send_message(combined_msg, reply_markup=reply_markup)
    
    # Сохраняем ID сообщения для последующего удаления
    if 'budget_change_message_ids' not in context.user_data:
        context.user_data['budget_change_message_ids'] = []
    context.user_data['budget_change_message_ids'].append(sent_message.message_id)

async def _display_restaurants_list(update, context, restaurants, language):
    """Отображает список ресторанов"""
    # Отправляем сообщение с рекомендацией
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    recommendation_msg = await translate_message('restaurant_recommendation', language)
    await update.effective_chat.send_message(recommendation_msg)

    # Формируем и отправляем информацию о каждом ресторане
    for r in restaurants:
        logger.info(f"[RESTAURANT_DISPLAY] Processing restaurant: {r['name']}")
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await asyncio.sleep(1)
        
        msg = f"• {r['name']}\n"
        
        # Переводим кухню с правильным контекстом и объединяем с ценой
        cuisine_and_price = ""
        if r.get('cuisine'):
            translated_cuisine = await translate_cuisine(r['cuisine'], language)
            cuisine_and_price = f"{translated_cuisine} - {r['average_check']}"
        else:
            cuisine_and_price = str(r['average_check'])
        msg += f"{cuisine_and_price}\n"
        
        # Переводим особенности
        if r.get('features'):
            features_text = r['features']
            if isinstance(features_text, list):
                features_text = ', '.join(features_text)
            translated_features = await translate_text(features_text, language)
            msg += f"{translated_features}\n"
            
        logger.info(f"[RESTAURANT_DISPLAY] Final message to send: {msg}")
        await update.effective_chat.send_message(msg)

    # Сохраняем информацию о ресторанах для последующего использования
    context.user_data['filtered_restaurants'] = restaurants
    logger.info(f"[RESTAURANT_DISPLAY] Saved {len(restaurants)} restaurants to context")

    # Создаем кнопки действий
    button_reserve = await translate_message('button_reserve', language)
    button_question = await translate_message('button_question', language)
    button_area = await translate_message('button_area', language)
    
    keyboard = [
        [
            InlineKeyboardButton(button_reserve, callback_data="book_restaurant"),
            InlineKeyboardButton(button_question, callback_data="ask_about_restaurant"),
            InlineKeyboardButton(button_area, callback_data="location_area")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    logger.info("[RESTAURANT_DISPLAY] Created keyboard with buttons")

    # Устанавливаем режим консультации
    context.user_data['consultation_mode'] = True
    context.user_data['restaurant_info'] = "\n".join([
        f"Restaurant: {r['name']}\nCuisine: {r.get('cuisine', '')}\nFeatures: {r.get('features', '')}" for r in restaurants
    ])

    # Отправляем приветственное сообщение
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(1)
    welcome_msg = await translate_message('consultation_welcome', language)
    logger.info(f"[RESTAURANT_DISPLAY] Sending welcome message with keyboard: {welcome_msg}")
    welcome_message = await update.effective_chat.send_message(welcome_msg, reply_markup=reply_markup)
    
    # Сохраняем ID приветственного сообщения с кнопками для последующего редактирования
    context.user_data['consultation_welcome_message_id'] = welcome_message.message_id
    logger.info(f"[RESTAURANT_DISPLAY] Saved welcome message ID: {welcome_message.message_id}")

async def translate_cuisine(cuisine_text: str, target_language: str) -> str:
    """Переводит тип кухни на целевой язык"""
    # Простой маппинг основных типов кухни
    cuisine_mapping = {
        'ru': {
            'Thai': 'Тайская',
            'Italian': 'Итальянская', 
            'Japanese': 'Японская',
            'Chinese': 'Китайская',
            'Indian': 'Индийская',
            'French': 'Французская',
            'Mediterranean': 'Средиземноморская',
            'Seafood': 'Морепродукты',
            'International': 'Интернациональная',
            'European': 'Европейская'
        }
    }
    
    if target_language in cuisine_mapping and cuisine_text in cuisine_mapping[target_language]:
        return cuisine_mapping[target_language][cuisine_text]
    
    # Если нет в маппинге, используем AI для перевода
    try:
        return await translate_text(cuisine_text, target_language)
    except Exception as e:
        logger.error(f"Error translating cuisine: {e}")
        return cuisine_text 