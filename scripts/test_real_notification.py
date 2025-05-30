#!/usr/bin/env python3
"""
Скрипт для тестирования реального уведомления менеджеру
"""

import sys
import os
import asyncio
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.bot.managers.booking_manager import BookingManager
from datetime import date, time

class MockUser:
    def __init__(self):
        self.id = 99999
        self.first_name = "Test"
        self.last_name = "User"
        self.username = "test_user"

async def test_real_notification():
    """Тестирует отправку уведомления на реальный контакт"""
    booking_data = {
        'date': date.today(),
        'time': time(19, 30),
        'guests': 2
    }
    user = MockUser()
    
    print("🧪 Тестируем уведомление для реального ресторана Etna")
    print("📞 Контакт: @alextex")
    print("=" * 50)
    
    try:
        await BookingManager._notify_restaurant(
            booking_number=9999,
            booking_data=booking_data,
            restaurant_contact="@alextex",
            user=user
        )
        print("✅ Тест завершен без ошибок")
        print("📋 Проверьте Telegram @alextex на наличие уведомления")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")

if __name__ == "__main__":
    asyncio.run(test_real_notification()) 