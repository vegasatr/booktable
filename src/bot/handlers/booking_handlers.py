"""
Обработчики callback'ов для процесса бронирования
"""
import logging
from datetime import datetime, date, time as datetime_time, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from ..managers.booking_manager import BookingManager
from ..ai.core import ai_generate
from ..ai.translation import translate_message

logger = logging.getLogger(__name__)

async def book_restaurant_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки РЕЗЕРВ - начинает процесс бронирования"""
    logger.info("[BOOKING] Book restaurant callback triggered")
    
    try:
        await BookingManager.start_booking_from_button(update, context)
    except Exception as e:
        logger.error(f"[BOOKING] Error in book_restaurant_callback: {e}")
        await update.effective_chat.send_message("Произошла ошибка при начале бронирования. Попробуйте позже.")

async def book_restaurant_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора конкретного ресторана из списка"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Извлекаем индекс ресторана из callback_data
        restaurant_index = int(query.data.split('_')[-1])
        restaurants = context.user_data.get('booking_data', {}).get('restaurants', [])
        
        if 0 <= restaurant_index < len(restaurants):
            restaurant = restaurants[restaurant_index]
            context.user_data['booking_data']['restaurant'] = restaurant
            context.user_data['booking_data']['step'] = 'time_selection'
            
            await BookingManager._ask_for_time(update, context, restaurant)
        else:
            await query.edit_message_text("Ошибка выбора ресторана. Попробуйте еще раз.")
            
    except Exception as e:
        logger.error(f"[BOOKING] Error in restaurant selection: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуйте еще раз.")

async def book_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора времени бронирования"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        
        if callback_data == "book_time_custom":
            # Пользователь выбрал "ДРУГОЕ" для времени
            restaurant = context.user_data['booking_data']['restaurant']
            await BookingManager._ask_for_custom_time(update, context, restaurant)
        else:
            # Пользователь выбрал конкретное время
            time_str = callback_data.split('_')[-1]  # Извлекаем время из "book_time_18:00"
            
            # Парсим время
            try:
                time_obj = datetime.strptime(time_str, "%H:%M").time()
                context.user_data['booking_data']['time'] = time_obj
                context.user_data['booking_data']['step'] = 'guests_selection'
                
                await BookingManager._ask_for_guests(update, context)
            except ValueError:
                await query.edit_message_text("Неверный формат времени. Попробуйте еще раз.")
                
    except Exception as e:
        logger.error(f"[BOOKING] Error in time selection: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуйте еще раз.")

async def book_guests_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора количества гостей"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        
        if callback_data == "book_guests_more":
            # Пользователь выбрал "БОЛЬШЕ" - запрашиваем кастомное количество
            await BookingManager._ask_for_custom_guests(update, context)
        else:
            # Пользователь выбрал конкретное количество гостей
            guests_count = int(callback_data.split('_')[-1])
            
            context.user_data['booking_data']['guests'] = guests_count
            context.user_data['booking_data']['step'] = 'date_selection'
            
            await BookingManager._ask_for_date(update, context)
        
    except Exception as e:
        logger.error(f"[BOOKING] Error in guests selection: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуйте еще раз.")

async def book_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора даты бронирования"""
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data
        
        if callback_data == "book_date_today":
            # Сегодня
            context.user_data['booking_data']['date'] = date.today()
            await BookingManager._complete_booking(update, context)
            
        elif callback_data == "book_date_tomorrow":
            # Завтра
            tomorrow = date.today() + timedelta(days=1)
            context.user_data['booking_data']['date'] = tomorrow
            await BookingManager._complete_booking(update, context)
            
        elif callback_data == "book_date_custom":
            # Пользователь выбрал "ДРУГОЕ" для даты
            await BookingManager._ask_for_custom_date(update, context)
            
    except Exception as e:
        logger.error(f"[BOOKING] Error in date selection: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуйте еще раз.")

async def handle_custom_time_input(update, context):
    """Обработчик ввода кастомного времени"""
    if context.user_data.get('booking_data', {}).get('step') != 'waiting_custom_time':
        return False
    
    text = update.message.text.strip()
    language = context.user_data.get('language', 'en')
    
    try:
        # Пытаемся распарсить время с помощью AI
        prompt = f"Parse this time: '{text}'. Return only time in HH:MM format (24-hour) or 'INVALID' if cannot parse."
        
        result = await ai_generate('parse_time', text=prompt, target_language='en')
        
        if result and result.strip() != 'INVALID':
            try:
                time_obj = datetime.strptime(result.strip(), "%H:%M").time()
                context.user_data['booking_data']['time'] = time_obj
                context.user_data['booking_data']['step'] = 'guests_selection'
                
                await BookingManager._ask_for_guests(update, context)
                return True
            except ValueError:
                pass
        
        # Если не удалось распарсить
        error_msg = await translate_message('booking_time_invalid', language)
        await update.message.reply_text(error_msg or "Неверный формат времени. Попробуйте еще раз (например: 19:30)")
        return True
        
    except Exception as e:
        logger.error(f"[BOOKING] Error parsing custom time: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
        return True

async def handle_custom_date_input(update, context):
    """Обработчик ввода кастомной даты"""
    if context.user_data.get('booking_data', {}).get('step') != 'waiting_custom_date':
        return False
    
    text = update.message.text.strip()
    language = context.user_data.get('language', 'en')
    
    try:
        # Пытаемся распарсить дату с помощью AI
        prompt = f"Parse this date: '{text}'. Today is {date.today().strftime('%d.%m.%Y')}. Return only date in DD.MM.YYYY format or 'INVALID' if cannot parse or date is in the past."
        
        result = await ai_generate('parse_date', text=prompt, target_language='en')
        
        if result and result.strip() != 'INVALID':
            try:
                date_obj = datetime.strptime(result.strip(), "%d.%m.%Y").date()
                
                # Проверяем что дата не в прошлом
                if date_obj >= date.today():
                    context.user_data['booking_data']['date'] = date_obj
                    await BookingManager._complete_booking(update, context)
                    return True
                    
            except ValueError:
                pass
        
        # Если не удалось распарсить
        error_msg = await translate_message('booking_date_invalid', language)
        await update.message.reply_text(error_msg or "Неверный формат даты. Попробуйте еще раз (например: 25.12.2024)")
        return True
        
    except Exception as e:
        logger.error(f"[BOOKING] Error parsing custom date: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
        return True

async def handle_custom_guests_input(update, context):
    """Обработчик ввода кастомного количества гостей"""
    if context.user_data.get('booking_data', {}).get('step') != 'waiting_custom_guests':
        return False
    
    text = update.message.text.strip()
    language = context.user_data.get('language', 'en')
    
    try:
        # Пытаемся распарсить количество гостей с помощью AI
        prompt = f"Parse this number of guests: '{text}'. Return only a number (1-50) or 'INVALID' if cannot parse or number is unreasonable."
        
        result = await ai_generate('parse_guests', text=prompt, target_language='en')
        
        if result and result.strip() != 'INVALID':
            try:
                guests_count = int(result.strip())
                
                # Проверяем разумные пределы
                if 1 <= guests_count <= 50:
                    context.user_data['booking_data']['guests'] = guests_count
                    context.user_data['booking_data']['step'] = 'date_selection'
                    
                    await BookingManager._ask_for_date(update, context)
                    return True
                    
            except ValueError:
                pass
        
        # Если не удалось распарсить
        await update.message.reply_text("Пожалуйста, укажите количество гостей числом (например: 8 или восемь)")
        return True
        
    except Exception as e:
        logger.error(f"[BOOKING] Error parsing custom guests: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
        return True

async def handle_booking_preferences(update, context):
    """Обработчик дополнительных пожеланий после завершения бронирования"""
    booking_number = context.user_data.get('current_booking_number')
    
    if not booking_number:
        return False
    
    text = update.message.text.strip()
    
    try:
        from ..database.bookings import update_booking_preferences
        
        # Обновляем пожелания в базе
        success = await update_booking_preferences(booking_number, text)
        
        if success:
            language = context.user_data.get('language', 'en')
            confirmation_msg = await translate_message('booking_preferences_saved', language)
            await update.message.reply_text(confirmation_msg or "Ваши пожелания сохранены и переданы в ресторан.")
            
            # TODO: Отправить дополнительное сообщение в ресторан
            # Пока просто логируем
            logger.info(f"[BOOKING] Additional preferences for booking #{booking_number}: {text}")
            
            # Очищаем номер бронирования
            context.user_data['current_booking_number'] = None
        else:
            await update.message.reply_text("Ошибка при сохранении пожеланий. Попробуйте еще раз.")
        
        return True
        
    except Exception as e:
        logger.error(f"[BOOKING] Error handling booking preferences: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
        return True 