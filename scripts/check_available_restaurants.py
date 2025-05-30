#!/usr/bin/env python3
"""
Скрипт для проверки доступных ресторанов в базе данных
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.bot.database.connection import get_db_connection
from psycopg2.extras import DictCursor

def check_available_restaurants():
    """Проверяет доступные рестораны в базе данных"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        print("🍽️ Доступные рестораны в базе данных:")
        print("=" * 50)
        
        cur.execute("SELECT name, booking_contact FROM restaurants WHERE active = 'true' ORDER BY name LIMIT 20;")
        restaurants = cur.fetchall()
        
        if restaurants:
            for r in restaurants:
                contact = r['booking_contact'] or 'НЕТ КОНТАКТА'
                print(f"  - {r['name']} (контакт: {contact})")
        else:
            print("  ❌ Нет активных ресторанов в базе")
            
        print(f"\nВсего активных ресторанов: {len(restaurants)}")
        
        # Проверим все рестораны независимо от статуса
        print("\n🔍 Проверяем ВСЕ рестораны в базе:")
        print("=" * 50)
        
        cur.execute("SELECT name, active, booking_contact FROM restaurants ORDER BY name LIMIT 20;")
        all_restaurants = cur.fetchall()
        
        if all_restaurants:
            for r in all_restaurants:
                contact = r['booking_contact'] or 'НЕТ КОНТАКТА'
                status = r['active'] or 'НЕТ СТАТУСА'
                print(f"  - {r['name']} (статус: {status}, контакт: {contact})")
        else:
            print("  ❌ Таблица restaurants пуста!")
            
        print(f"\nВсего ресторанов в базе: {len(all_restaurants)}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при проверке ресторанов: {e}")

if __name__ == "__main__":
    check_available_restaurants() 