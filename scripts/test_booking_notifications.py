#!/usr/bin/env python3
"""
Скрипт для тестирования уведомлений менеджерам ресторанов
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from datetime import date, time
from src.bot.managers.booking_manager import BookingManager

# Mock user объект для тестирования
class MockUser:
    def __init__(self):
        self.id = 99999
        self.first_name = "Test"
        self.last_name = "User"
        self.username = "test_user"

async def test_notification_system():
    """Тестирует систему уведомлений менеджерам"""
    print("🧪 Тестируем систему уведомлений менеджерам ресторанов")
    print("=" * 60)
    
    # Тестовые данные бронирования
    booking_data = {
        'date': date.today(),
        'time': time(19, 30),
        'guests': 3
    }
    
    user = MockUser()
    
    # Тестируем разные типы контактов
    test_contacts = [
        "@test_username",
        "https://t.me/test_restaurant", 
        "1234567890",  # Chat ID
        "+66987654321",  # Телефон
        "invalid_contact",  # Неверный формат
        "",  # Пустой контакт
    ]
    
    for i, contact in enumerate(test_contacts, 1):
        print(f"\n🔍 Тест {i}: Контакт '{contact}'")
        try:
            # Вызываем функцию уведомления
            await BookingManager._notify_restaurant(
                booking_number=2000 + i,
                booking_data=booking_data,
                restaurant_contact=contact,
                user=user
            )
            print(f"✅ Уведомление обработано без ошибок")
            
        except Exception as e:
            print(f"❌ Ошибка при отправке уведомления: {e}")
    
    print("\n" + "=" * 60)
    print("📋 Проверьте логи бота для подробностей отправки уведомлений")
    print("   Команда: tail -f /root/booktable_bot/logs/bot.log | grep BOOKING")

def check_restaurant_contacts():
    """Проверяет контакты ресторанов в базе данных"""
    try:
        from src.bot.database.connection import get_db_connection
        from psycopg2.extras import DictCursor
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        print("\n📋 Контакты ресторанов для уведомлений:")
        print("-" * 50)
        
        cur.execute("""
            SELECT name, booking_contact, phone, website 
            FROM restaurants 
            WHERE booking_contact IS NOT NULL AND booking_contact != ''
            ORDER BY name
            LIMIT 10;
        """)
        
        restaurants = cur.fetchall()
        
        if restaurants:
            for rest in restaurants:
                print(f"🍽️ {rest['name']}")
                print(f"   📞 booking_contact: {rest['booking_contact']}")
                print(f"   📱 phone: {rest['phone']}")
                print(f"   🌐 website: {rest['website']}")
                print()
        else:
            print("❌ Нет ресторанов с контактами для уведомлений")
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при получении контактов ресторанов: {e}")

async def main():
    """Основная функция"""
    # Проверяем контакты в базе
    check_restaurant_contacts()
    
    # Тестируем уведомления
    await test_notification_system()

if __name__ == "__main__":
    asyncio.run(main()) 