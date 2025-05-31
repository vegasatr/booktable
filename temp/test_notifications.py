#!/usr/bin/env python3
"""
Тестирование системы уведомлений с рабочими контактами
"""

import sys
import os
import asyncio
from datetime import date, time as datetime_time
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.bot.managers.booking_manager import BookingManager

class MockUser:
    def __init__(self):
        self.id = 5419235215  # Реальный ID alextex
        self.username = "alextex"
        self.first_name = "АLEX"
        self.last_name = ""

async def test_notification_system():
    """Тестирует полную систему уведомлений"""
    print("🧪 ТЕСТ СИСТЕМЫ УВЕДОМЛЕНИЙ")
    print("=" * 50)
    
    # Тестовые данные бронирования
    booking_data = {
        'date': date.today(),
        'time': datetime_time(19, 30),
        'guests': 2,
        'restaurant': {'name': 'Test Restaurant'}
    }
    
    user = MockUser()
    
    # Тестируем разные типы контактов
    test_contacts = [
        ("Telegram username", "@alextex"),
        ("Username с префиксом =", "=@alextex"),
        ("Chat ID", "5419235215"),  # ID alextex'а
        ("Пустой контакт", ""),
    ]
    
    for i, (desc, contact) in enumerate(test_contacts, 1):
        print(f"\n🔍 Тест {i}: {desc} -> '{contact}'")
        try:
            await BookingManager._notify_restaurant(
                booking_number=9000 + i,
                booking_data=booking_data,
                restaurant_contact=contact,
                user=user
            )
            print(f"✅ Уведомление обработано")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    print("\n" + "=" * 50)
    print("📋 Результаты в логах: tail -f logs/bot.log | grep BOOKING")

if __name__ == "__main__":
    asyncio.run(test_notification_system()) 