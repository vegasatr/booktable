"""
Модуль для работы с бронированиями в базе данных
"""
import logging
from datetime import datetime, date, time as datetime_time
from psycopg2.extras import DictCursor
from .connection import get_db_connection

logger = logging.getLogger(__name__)

async def save_booking_to_db(restaurant_name, client_name, phone, date_booking, time_booking, 
                            guests, restaurant_contact, booking_method="telegram", 
                            preferences="", client_code="", status="pending"):
    """
    Сохраняет бронирование в базу данных
    
    Args:
        restaurant_name: Название ресторана
        client_name: Имя клиента
        phone: Телефон клиента
        date_booking: Дата бронирования (date объект)
        time_booking: Время бронирования (time объект)
        guests: Количество гостей (int)
        restaurant_contact: Контакт ресторана для уведомлений
        booking_method: Способ бронирования (по умолчанию telegram)
        preferences: Особые пожелания клиента
        client_code: Код клиента (telegram_user_id)
        status: Статус бронирования (pending, confirmed, cancelled)
    
    Returns:
        int: booking_number при успехе, None при ошибке
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Вставляем бронирование
        insert_query = """
            INSERT INTO bookings (
                date, time, client_name, phone, guests, restaurant, 
                booking_method, restaurant_contact, preferences, 
                client_code, status, comment
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING booking_number
        """
        
        values = (
            date_booking, time_booking, client_name, phone, guests, restaurant_name,
            booking_method, restaurant_contact, preferences, str(client_code), status, ""
        )
        
        cur.execute(insert_query, values)
        booking_number = cur.fetchone()['booking_number']
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"[BOOKINGS] Saved booking #{booking_number} for {restaurant_name}")
        return booking_number
        
    except Exception as e:
        logger.error(f"[BOOKINGS] Error saving booking: {e}")
        if conn:
            conn.rollback()
            cur.close()
            conn.close()
        return None

async def get_booking_by_number(booking_number):
    """
    Получает бронирование по номеру
    
    Args:
        booking_number: Номер бронирования
    
    Returns:
        dict: Данные бронирования или None
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        cur.execute("""
            SELECT * FROM bookings 
            WHERE booking_number = %s
        """, (booking_number,))
        
        booking = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return dict(booking) if booking else None
        
    except Exception as e:
        logger.error(f"[BOOKINGS] Error getting booking #{booking_number}: {e}")
        return None

async def update_booking_preferences(booking_number, additional_preferences):
    """
    Добавляет дополнительные пожелания к бронированию
    
    Args:
        booking_number: Номер бронирования
        additional_preferences: Дополнительные пожелания
    
    Returns:
        bool: True при успехе, False при ошибке
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Получаем текущие пожелания
        cur.execute("SELECT preferences FROM bookings WHERE booking_number = %s", (booking_number,))
        current = cur.fetchone()
        
        if not current:
            return False
            
        # Объединяем пожелания
        current_prefs = current['preferences'] or ""
        new_prefs = f"{current_prefs}\n{additional_preferences}".strip()
        
        # Обновляем
        cur.execute("""
            UPDATE bookings 
            SET preferences = %s 
            WHERE booking_number = %s
        """, (new_prefs, booking_number))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"[BOOKINGS] Updated preferences for booking #{booking_number}")
        return True
        
    except Exception as e:
        logger.error(f"[BOOKINGS] Error updating booking preferences: {e}")
        if conn:
            conn.rollback()
            cur.close()
            conn.close()
        return False

async def get_restaurant_working_hours(restaurant_name):
    """
    Получает время работы ресторана
    
    Args:
        restaurant_name: Название ресторана
    
    Returns:
        dict: Время работы или None
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        cur.execute("""
            SELECT working_hours, booking_method, booking_contact
            FROM restaurants 
            WHERE name = %s AND active = 'true'
        """, (restaurant_name,))
        
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return dict(result) if result else None
        
    except Exception as e:
        logger.error(f"[BOOKINGS] Error getting restaurant working hours: {e}")
        return None 