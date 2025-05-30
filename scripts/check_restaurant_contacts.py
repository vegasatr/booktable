#!/usr/bin/env python3
"""
Скрипт для проверки контактов ресторанов из реальных бронирований
"""

import sys
import os
import asyncio
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.bot.database.bookings import get_restaurant_working_hours

async def check_restaurant_contacts():
    """Проверяет контакты ресторанов из реальных бронирований"""
    restaurants = ['WeCafe Rawai', 'Nitan', 'Etna', 'Thai Corner', 'Solo Restaurant', 'Test Restaurant']
    
    print("🔍 Проверяем контакты ресторанов из реальных бронирований:")
    print("=" * 60)
    
    for name in restaurants:
        try:
            data = await get_restaurant_working_hours(name)
            if data:
                contact = data.get('booking_contact')
                method = data.get('booking_method')
                print(f"🍽️ {name}:")
                print(f"   📞 booking_contact: '{contact}'")
                print(f"   📋 booking_method: '{method}'")
                print(f"   📊 data: {data}")
                
                if contact:
                    print(f"   ✅ Контакт есть")
                else:
                    print(f"   ❌ Контакт отсутствует!")
            else:
                print(f"🍽️ {name}: ❌ Ресторан не найден в базе")
            print()
        except Exception as e:
            print(f"🍽️ {name}: ❌ Ошибка: {e}")
            print()

if __name__ == "__main__":
    asyncio.run(check_restaurant_contacts()) 