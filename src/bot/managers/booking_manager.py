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
from ..database.connection import get_db_connection
from psycopg2.extras import DictCursor
from ..config import TELEGRAM_TOKEN

# Добавляем токен бота менеджеров
BOOKINGS_BOT_TOKEN = "7753935644:AAH9CNbhe1sptlJj8VFtg7aQRSKnRNswqf8"

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
        
        logger.info(f"[BOOKING] _ask_for_time: language={language}, user_data keys: {list(context.user_data.keys())}")
        
        question = await translate_message('booking_time_question', language)
        
        # Генерируем варианты времени (через 15 минут от текущего + 4 слота по 30 мин)
        now = datetime.now()
        start_time = now + timedelta(minutes=15)
        
        # ИСПРАВЛЕНО: Округляем время ВВЕРХ до ближайших 00 или 30 минут
        if start_time.minute < 30:
            # Если время до 30 минут - округляем до 30
            start_time = start_time.replace(minute=30, second=0, microsecond=0)
        elif start_time.minute > 30:
            # Если время после 30 минут - округляем до следующего часа
            start_time = start_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            # Если точно 30 минут - переходим к следующему часу (следующий слот)
            start_time = start_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        logger.info(f"[BOOKING] Current time: {now.strftime('%H:%M')}, suggested start time: {start_time.strftime('%H:%M')}")
        
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
        
        # Кнопки с количеством гостей 1-5 + кнопка "БОЛЬШЕ"
        guest_buttons = []
        for i in range(1, 6):
            guest_buttons.append(InlineKeyboardButton(
                str(i), callback_data=f"book_guests_{i}"
            ))
        
        # Добавляем кнопку "БОЛЬШЕ" для случая когда гостей больше 5
        more_button = InlineKeyboardButton("БОЛЬШЕ", callback_data="book_guests_more")
        
        keyboard = InlineKeyboardMarkup([
            guest_buttons,  # Кнопки 1-5 в одном ряду
            [more_button]   # Кнопка "БОЛЬШЕ" в отдельном ряду
        ])
        
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
    async def _ask_for_custom_guests(update, context):
        """Спрашивает кастомное количество гостей"""
        language = context.user_data.get('language', 'en')
        
        question = await translate_message('booking_custom_guests', language)
        
        # Убираем кнопки, ждем текстовый ввод
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(question)
        else:
            await update.message.reply_text(question)
        
        # Устанавливаем состояние ожидания количества гостей
        context.user_data['booking_data']['step'] = 'waiting_custom_guests'
    
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
        confirmation = await translate_message('booking_confirmation', language, booking_number=booking_number)
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
        """Отправляет уведомление в ресторан о новом бронировании через бот менеджеров"""
        try:
            # Формируем сообщение для ресторана согласно ТЗ
            client_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if not client_name:
                client_name = user.username or f"User_{user.id}"
            
            # Новый формат уведомления для бота менеджеров
            message = f"""🆕 НОВОЕ БРОНИРОВАНИЕ

🔢 Номер брони: #{booking_number}
👤 Клиент: {client_name}
📅 Дата: {booking_data['date'].strftime('%d.%m.%Y')}
⏰ Время: {booking_data['time'].strftime('%H:%M')}
👥 Гостей: {booking_data['guests']}
📱 Telegram: @{user.username or user.id}

✅ Бронирование ожидает подтверждения"""
            
            # Получаем название ресторана из booking_data
            restaurant_name = booking_data.get('restaurant', {}).get('name', 'Unknown Restaurant')
            
            # Отправляем уведомление через бот менеджеров
            success = await BookingManager._send_to_managers_bot(
                booking_number=booking_number,
                restaurant_name=restaurant_name,
                message=message,
                contact=restaurant_contact
            )
            
            if success:
                logger.info(f"[BOOKING] Notification sent via managers bot for booking #{booking_number}")
            else:
                logger.warning(f"[BOOKING] Failed to send via managers bot, falling back to direct send")
                # Fallback - отправляем напрямую как раньше
                await BookingManager._send_direct_notification(booking_number, message, restaurant_contact)
            
        except Exception as e:
            logger.error(f"[BOOKING] Error notifying restaurant: {e}")
            logger.info(f"[BOOKING] Manual notification needed due to error: {message}")
    
    @staticmethod
    async def _send_to_managers_bot(booking_number, restaurant_name, message, contact):
        """Отправляет уведомление через бот менеджеров"""
        try:
            # Используем бот менеджеров для отправки
            managers_bot = Bot(token=BOOKINGS_BOT_TOKEN)
            
            # Находим всех менеджеров этого ресторана по базе данных
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            
            # Получаем всех авторизованных менеджеров для этого ресторана
            # Это будет реализовано когда менеджеры подключатся к боту
            # Пока логируем что уведомление готово
            logger.info(f"[BOOKING] Managers bot notification prepared for {restaurant_name}: {message}")
            
            # Пытаемся отправить напрямую по контакту если это @username
            if contact and contact.startswith('@'):
                username = contact[1:]  # убираем @
                try:
                    chat = await managers_bot.get_chat(username)
                    await managers_bot.send_message(chat_id=chat.id, text=message)
                    logger.info(f"[BOOKING] Notification sent to @{username} via managers bot for booking #{booking_number}")
                    return True
                except Exception as e:
                    logger.warning(f"[BOOKING] Failed to send to @{username} via managers bot: {e}")
                    return False
            
            cur.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"[BOOKING] Error sending via managers bot: {e}")
            return False
    
    @staticmethod
    async def _send_direct_notification(booking_number, message, restaurant_contact):
        """Отправляет уведомление напрямую (fallback метод)"""
        try:
            # Старый код для прямой отправки через основного бота
            if not restaurant_contact:
                logger.warning(f"[BOOKING] No restaurant contact for booking #{booking_number}")
                return
            
            clean_contact = restaurant_contact.strip()
            if clean_contact.startswith('='):
                clean_contact = clean_contact[1:]
            
            bot = Bot(token=TELEGRAM_TOKEN)
            
            if clean_contact.startswith('@'):
                username = clean_contact[1:]
                try:
                    chat = await bot.get_chat(username)
                    await bot.send_message(chat_id=chat.id, text=message)
                    logger.info(f"[BOOKING] Direct notification sent to @{username} for booking #{booking_number}")
                except Exception as e:
                    logger.warning(f"[BOOKING] Failed direct send to @{username}: {e}")
            else:
                logger.info(f"[BOOKING] Non-username contact format: {clean_contact}")
                
        except Exception as e:
            logger.error(f"[BOOKING] Error in direct notification: {e}")
    
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