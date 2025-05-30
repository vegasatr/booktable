#!/usr/bin/env python3
"""
Скрипт для проверки сохранения бронирования в базе данных
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.bot.database.connection import get_db_connection
from psycopg2.extras import DictCursor

def check_test_booking():
    """Проверяет тестовое бронирование в базе"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        print("📋 Проверяем тестовое бронирование #1000 в базе данных:")
        
        cur.execute('SELECT * FROM bookings WHERE booking_number = 1000;')
        booking = cur.fetchone()
        
        if booking:
            print('✅ Тестовое бронирование найдено:')
            for key, value in dict(booking).items():
                print(f'  - {key}: {value}')
            
            # Проверяем обязательные поля
            required_fields = ['restaurant', 'client_name', 'date', 'time', 'guests', 'status']
            missing_fields = []
            
            for field in required_fields:
                if not booking.get(field):
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"⚠️ Отсутствуют обязательные поля: {missing_fields}")
            else:
                print("✅ Все обязательные поля заполнены")
                
            return True
        else:
            print('❌ Тестовое бронирование #1000 не найдено в базе')
            return False
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при проверке бронирования: {e}")
        return False

def check_all_bookings():
    """Показывает все бронирования в базе"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        print("\n📋 Все бронирования в базе данных:")
        
        cur.execute('SELECT booking_number, restaurant, client_name, date, time, guests, status FROM bookings ORDER BY booking_number;')
        bookings = cur.fetchall()
        
        if bookings:
            for booking in bookings:
                print(f"  #{booking['booking_number']}: {booking['restaurant']} - {booking['client_name']} - {booking['date']} {booking['time']} ({booking['guests']} guests) - {booking['status']}")
        else:
            print("  Нет бронирований в базе")
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при получении списка бронирований: {e}")

if __name__ == "__main__":
    check_test_booking()
    check_all_bookings() 