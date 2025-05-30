"""
Модуль управления бронированиями ресторанов
Реализует полный цикл бронирования согласно ТЗ
"""
import logging
import asyncio
from datetime import datetime, date, time as datetime_time, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from ..ai.core import ai_generate, is_about_restaurants
from ..ai.translation import translate_message
from ..database.bookings import (
    save_booking_to_db, update_booking_preferences, 
    get_restaurant_working_hours
)
from ..config import TELEGRAM_TOKEN

logger = logging.getLogger(__name__)

class BookingManager:
    """Управляет процессом бронирования ресторанов"""
    
    @staticmethod
    async def start_booking_from_button(update, context):
        """
        Начинает бронирование по нажатию кнопки РЕЗЕРВ
        Два сценария:
        1. Один ресторан в фильтре -> сразу к бронированию
        2. Несколько ресторанов -> выбор ресторана
        """
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        language = context.user_data.get('language', 'en')
        
        # Получаем рестораны из контекста
        restaurants = context.user_data.get('filtered_restaurants', [])
        
        if not restaurants:
            error_msg = await translate_message('no_restaurants_found', language)
            await query.edit_message_text(error_msg)
            return
        
        # Инициализируем данные бронирования
        context.user_data['booking_data'] = {
            'user_id': user_id,
            'restaurants': restaurants,
            'step': 'restaurant_selection'
        }
        
        if len(restaurants) == 1:
            # Один ресторан - сразу к выбору времени
            restaurant = restaurants[0]
            context.user_data['booking_data']['restaurant'] = restaurant
            context.user_data['booking_data']['step'] = 'time_selection'
            
            await BookingManager._ask_for_time(update, context, restaurant)
        else:
            # Несколько ресторанов - выбор ресторана
            await BookingManager._ask_which_restaurant(update, context, restaurants)
    
    @staticmethod
    async def start_booking_from_chat(update, context, message_text):
        """
        Начинает бронирование из сообщения в чате
        Анализирует контекст и определяет ресторан для бронирования
        """
        user_id = update.effective_user.id
        language = context.user_data.get('language', 'en')
        
        # Проверяем есть ли рестораны в контексте
        restaurants = context.user_data.get('filtered_restaurants', [])
        
        if not restaurants:
            # Нет ресторанов в контексте - просим уточнить
            response = await ai_generate('clarify_restaurant_for_booking', 
                                       text=message_text, target_language=language)
            await update.message.reply_text(response)
            return
        
        # Пытаемся определить ресторан из сообщения
        restaurant_name = await BookingManager._extract_restaurant_from_message(
            message_text, restaurants, language
        )
        
        # Инициализируем данные бронирования  
        context.user_data['booking_data'] = {
            'user_id': user_id,
            'restaurants': restaurants,
            'step': 'restaurant_selection'
        }
        
        if restaurant_name:
            # Найден конкретный ресторан
            restaurant = next((r for r in restaurants if r['name'] == restaurant_name), None)
            if restaurant:
                context.user_data['booking_data']['restaurant'] = restaurant
                context.user_data['booking_data']['step'] = 'time_selection'
                
                await BookingManager._ask_for_time(update, context, restaurant)
                return
        
        # Не удалось определить ресторан - выбор из списка
        await BookingManager._ask_which_restaurant(update, context, restaurants)
    
    @staticmethod
    async def _ask_which_restaurant(update, context, restaurants):
        """Спрашивает какой ресторан бронировать"""
        language = context.user_data.get('language', 'en')
        
        question = await translate_message('booking_which_restaurant', language)
        
        # Формируем список ресторанов
        restaurant_list = []
        buttons = []
        
        for i, restaurant in enumerate(restaurants, 1):
            restaurant_list.append(f"{i}. {restaurant['name']}")
            buttons.append([InlineKeyboardButton(
                str(i), callback_data=f"book_restaurant_{i-1}"
            )])
        
        message_text = f"{question}\n\n" + "\n".join(restaurant_list)
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(message_text, reply_markup=keyboard)
        else:
            await update.message.reply_text(message_text, reply_markup=keyboard)
    
    @staticmethod
    async def _ask_for_time(update, context, restaurant):
        """Спрашивает время бронирования"""
        language = context.user_data.get('language', 'en')
        
        question = await translate_message('booking_time_question', language)
        
        # Генерируем варианты времени (через 15 минут от текущего + 4 слота по 30 мин)
        now = datetime.now()
        start_time = now + timedelta(minutes=15)
        start_time = start_time.replace(minute=0 if start_time.minute < 30 else 30, second=0, microsecond=0)
        
        time_buttons = []
        for i in range(4):
            time_slot = start_time + timedelta(minutes=i*30)
            time_str = time_slot.strftime("%H:%M")
            time_buttons.append(InlineKeyboardButton(
                time_str, callback_data=f"book_time_{time_str}"
            ))
        
        # Кнопка "ДРУГОЕ"
        other_button = InlineKeyboardButton("ДРУГОЕ", callback_data="book_time_custom")
        
        keyboard = InlineKeyboardMarkup([
            time_buttons[:2],  # Первые 2 времени
            time_buttons[2:],  # Следующие 2 времени  
            [other_button]     # Кнопка "ДРУГОЕ"
        ])
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(question, reply_markup=keyboard)
        else:
            await update.message.reply_text(question, reply_markup=keyboard)
    
    @staticmethod
    async def _ask_for_custom_time(update, context, restaurant):
        """Спрашивает кастомное время с учетом времени работы ресторана"""
        language = context.user_data.get('language', 'en')
        
        # Получаем время работы ресторана
        restaurant_data = await get_restaurant_working_hours(restaurant['name'])
        closing_time = "11 PM"  # По умолчанию
        
        if restaurant_data and restaurant_data.get('working_hours'):
            # TODO: Парсить working_hours из JSONB
            # Пока используем дефолтное время
            pass
        
        question = await translate_message('booking_custom_time', language, closing_time=closing_time)
        
        # Убираем кнопки, ждем текстовый ввод
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(question)
        else:
            await update.message.reply_text(question)
        
        # Устанавливаем состояние ожидания времени
        context.user_data['booking_data']['step'] = 'waiting_custom_time'
    
    @staticmethod
    async def _ask_for_guests(update, context):
        """Спрашивает количество гостей"""
        language = context.user_data.get('language', 'en')
        
        question = await translate_message('booking_guests_question', language)
        
        # Кнопки с количеством гостей
        guest_buttons = []
        for i in range(1, 6):
            guest_buttons.append(InlineKeyboardButton(
                str(i), callback_data=f"book_guests_{i}"
            ))
        
        keyboard = InlineKeyboardMarkup([guest_buttons])
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(question, reply_markup=keyboard)
        else:
            await update.message.reply_text(question, reply_markup=keyboard)
    
    @staticmethod
    async def _ask_for_date(update, context):
        """Спрашивает дату бронирования"""
        language = context.user_data.get('language', 'en')
        
        question = await translate_message('booking_date_question', language)
        
        date_buttons = [
            InlineKeyboardButton("СЕГОДНЯ", callback_data="book_date_today"),
            InlineKeyboardButton("ЗАВТРА", callback_data="book_date_tomorrow"),
            InlineKeyboardButton("ДРУГОЕ", callback_data="book_date_custom")
        ]
        
        keyboard = InlineKeyboardMarkup([date_buttons])
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(question, reply_markup=keyboard)
        else:
            await update.message.reply_text(question, reply_markup=keyboard)
    
    @staticmethod
    async def _ask_for_custom_date(update, context):
        """Спрашивает кастомную дату"""
        language = context.user_data.get('language', 'en')
        
        question = await translate_message('booking_custom_date', language)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(question)
        else:
            await update.message.reply_text(question)
        
        # Устанавливаем состояние ожидания даты
        context.user_data['booking_data']['step'] = 'waiting_custom_date'
    
    @staticmethod
    async def _complete_booking(update, context):
        """Завершает бронирование и отправляет уведомления"""
        language = context.user_data.get('language', 'en')
        booking_data = context.user_data['booking_data']
        
        # Получаем данные пользователя
        user = update.effective_user
        client_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        if not client_name:
            client_name = user.username or f"User_{user.id}"
        
        # Получаем контакт ресторана
        restaurant = booking_data['restaurant']
        restaurant_data = await get_restaurant_working_hours(restaurant['name'])
        restaurant_contact = restaurant_data.get('booking_contact') if restaurant_data else None
        
        # Сохраняем бронирование в базу
        booking_number = await save_booking_to_db(
            restaurant_name=restaurant['name'],
            client_name=client_name,
            phone="",  # Заполнится при необходимости
            date_booking=booking_data['date'],
            time_booking=booking_data['time'],
            guests=booking_data['guests'],
            restaurant_contact=restaurant_contact or "",
            booking_method="telegram",
            preferences="",
            client_code=user.id,
            status="pending"
        )
        
        if not booking_number:
            await update.effective_chat.send_message("Ошибка при сохранении бронирования. Попробуйте позже.")
            return
        
        # Сохраняем номер бронирования для последующих дополнений
        context.user_data['current_booking_number'] = booking_number
        
        # Отправляем подтверждение пользователю
        confirmation = await translate_message('booking_confirmation', language)
        instructions = await translate_message('booking_instructions', language)
        
        await update.effective_chat.send_message(confirmation)
        await update.effective_chat.send_message(instructions)
        
        # Отправляем уведомление в ресторан
        if restaurant_contact:
            await BookingManager._notify_restaurant(booking_number, booking_data, restaurant_contact, user)
        
        # Очищаем данные бронирования
        context.user_data['booking_data'] = None
        context.user_data['booking_step'] = 'completed'
    
    @staticmethod
    async def _notify_restaurant(booking_number, booking_data, restaurant_contact, user):
        """Отправляет уведомление в ресторан о новом бронировании"""
        try:
            # Формируем сообщение для ресторана
            client_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if not client_name:
                client_name = user.username or f"User_{user.id}"
            
            message = f"""🍽️ НОВОЕ БРОНИРОВАНИЕ - BookTable
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Номер брони: #{booking_number}
👤 Клиент: {client_name}
📅 Дата: {booking_data['date'].strftime('%d.%m.%Y')}
🕐 Время: {booking_data['time'].strftime('%H:%M')}
👥 Гостей: {booking_data['guests']}
📱 Контакт: @{user.username or user.id}

Если у клиента будут особые пожелания к столику или блюдам, я передам их дополнительно.

С уважением, BookTable Bot 🤖"""
            
            # Очищаем контакт от лишних символов (= в начале)
            clean_contact = restaurant_contact.strip()
            if clean_contact.startswith('='):
                clean_contact = clean_contact[1:]
            
            # Отправляем уведомление в ресторан
            if clean_contact:
                bot = Bot(token=TELEGRAM_TOKEN)
                
                # Определяем тип контакта и отправляем сообщение
                if clean_contact.startswith('@'):
                    # Telegram username - отправляем в личные сообщения
                    username = clean_contact[1:]  # убираем @
                    try:
                        # Сначала пытаемся найти пользователя
                        chat = await bot.get_chat(username)
                        await bot.send_message(chat_id=chat.id, text=message)
                        logger.info(f"[BOOKING] Notification sent to @{username} for booking #{booking_number}")
                    except Exception as username_error:
                        logger.warning(f"[BOOKING] Failed to send to @{username}: {username_error}")
                        # Логируем для ручной отправки
                        logger.info(f"[BOOKING] Manual notification needed to @{username}: {message}")
                        
                elif clean_contact.startswith('https://t.me/'):
                    # Telegram link - извлекаем username
                    username = clean_contact.split('/')[-1]
                    if username.startswith('+'):
                        # Это номер телефона, не username
                        logger.warning(f"[BOOKING] Phone number link not supported: {clean_contact}")
                        logger.info(f"[BOOKING] Manual notification needed to {clean_contact}: {message}")
                    else:
                        try:
                            chat = await bot.get_chat(username)
                            await bot.send_message(chat_id=chat.id, text=message)
                            logger.info(f"[BOOKING] Notification sent to {username} for booking #{booking_number}")
                        except Exception as link_error:
                            logger.warning(f"[BOOKING] Failed to send to {username}: {link_error}")
                            logger.info(f"[BOOKING] Manual notification needed to {clean_contact}: {message}")
                            
                elif clean_contact.isdigit() or (clean_contact.startswith('-') and clean_contact[1:].isdigit()):
                    # Telegram chat ID (может быть отрицательным для групп)
                    try:
                        await bot.send_message(chat_id=int(clean_contact), text=message)
                        logger.info(f"[BOOKING] Notification sent to chat_id {clean_contact} for booking #{booking_number}")
                    except Exception as chat_error:
                        logger.warning(f"[BOOKING] Failed to send to chat_id {clean_contact}: {chat_error}")
                        logger.info(f"[BOOKING] Manual notification needed to {clean_contact}: {message}")
                        
                elif clean_contact.startswith('+') and clean_contact[1:].replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isdigit():
                    # Номер телефона - пытаемся отправить как есть (возможно это зарегистрированный Telegram ID)
                    phone_digits = clean_contact[1:].replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                    try:
                        # Пытаемся отправить на номер телефона как chat_id
                        await bot.send_message(chat_id=int(phone_digits), text=message)
                        logger.info(f"[BOOKING] Notification sent to phone-based chat_id {phone_digits} for booking #{booking_number}")
                    except Exception as phone_error:
                        logger.warning(f"[BOOKING] Failed to send to phone {clean_contact}: {phone_error}")
                        logger.info(f"[BOOKING] Manual notification needed - phone number may not be registered in Telegram: {clean_contact}")
                        logger.info(f"[BOOKING] Message to send manually: {message}")
                        
                elif clean_contact.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isdigit():
                    # Просто цифры без + (возможно телефон без +, возможно ID)
                    clean_digits = clean_contact.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                    try:
                        # Пытаемся отправить как chat_id
                        await bot.send_message(chat_id=int(clean_digits), text=message)
                        logger.info(f"[BOOKING] Notification sent to chat_id/phone {clean_digits} for booking #{booking_number}")
                    except Exception as digits_error:
                        logger.warning(f"[BOOKING] Failed to send to {clean_contact}: {digits_error}")
                        logger.info(f"[BOOKING] Manual notification needed to {clean_contact}: {message}")
                        
                else:
                    # Неизвестный формат контакта
                    logger.warning(f"[BOOKING] Unknown contact format: {clean_contact}")
                    logger.info(f"[BOOKING] Manual notification needed to {clean_contact}: {message}")
            else:
                # Нет контакта ресторана
                logger.warning(f"[BOOKING] No restaurant contact for booking #{booking_number}")
                logger.info(f"[BOOKING] Manual notification needed (no contact): {message}")
            
        except Exception as e:
            logger.error(f"[BOOKING] Error notifying restaurant: {e}")
            # В случае ошибки все равно логируем сообщение для ручной отправки
            logger.info(f"[BOOKING] Manual notification needed due to error: {message}")
    
    @staticmethod
    async def _extract_restaurant_from_message(message_text, restaurants, language):
        """Извлекает название ресторана из сообщения пользователя"""
        try:
            # Создаем список названий ресторанов для AI
            restaurant_names = [r['name'] for r in restaurants]
            restaurant_list = ", ".join(restaurant_names)
            
            # Просим AI определить ресторан
            prompt = f"User message: '{message_text}'. Available restaurants: {restaurant_list}. Which restaurant does the user want to book? Reply only with the exact restaurant name or 'UNKNOWN' if unclear."
            
            result = await ai_generate('extract_restaurant_name', 
                                     text=prompt, target_language='en')
            
            # Проверяем результат
            if result and result.strip() in restaurant_names:
                return result.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"[BOOKING] Error extracting restaurant from message: {e}")
            return None 