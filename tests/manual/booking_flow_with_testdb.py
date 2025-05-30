#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FLOW ТЕСТ БРОНИРОВАНИЯ С ТЕСТОВОЙ БД
==================================

Полный flow тест бронирования с использованием реальной тестовой базы данных.
Требует созданную тестовую БД (scripts/create_test_db.sh).
"""

import sys
import os
import asyncio
from datetime import date, time, datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# Добавляем корень проекта в PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

class TestDBFlowTester:
    """Тестер flow бронирования с реальной тестовой БД"""
    
    def __init__(self):
        # Патчим connection.py чтобы использовать тестовую БД
        self.patch_connection()
        
    def patch_connection(self):
        """Подменяет connection.py на тестовую версию"""
        # Импортируем тестовое соединение
        from src.bot.database.test_connection import get_db_connection as test_get_db_connection
        
        # Патчим все модули которые используют БД
        import src.bot.database.bookings
        src.bot.database.bookings.get_db_connection = test_get_db_connection
        
        print("🔧 Подключение переключено на тестовую БД")
    
    def create_mock_update(self, user_id=12345, username="testuser", 
                          first_name="Test", last_name="User"):
        """Создает mock объект update"""
        update = Mock()
        query = Mock()
        
        # Настройка callback query
        update.callback_query = query
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.message = Mock()
        query.message.reply_text = AsyncMock()
        
        # Настройка пользователя
        update.effective_user = Mock()
        update.effective_user.id = user_id
        update.effective_user.username = username
        update.effective_user.first_name = first_name
        update.effective_user.last_name = last_name
        
        # Настройка чата
        update.effective_chat = Mock()
        update.effective_chat.send_message = AsyncMock()
        
        # Настройка сообщения
        update.message = Mock()
        update.message.text = ""
        update.message.reply_text = AsyncMock()
        
        return update
    
    def create_mock_context(self, restaurants=None, language='en'):
        """Создает mock объект context"""
        context = Mock()
        
        if restaurants is None:
            # Используем реальные тестовые рестораны из БД
            restaurants = [
                {
                    'name': 'Test Italian Restaurant',
                    'cuisine': 'Italian',
                    'working_hours': {'close': '23:00'}
                }
            ]
        
        context.user_data = {
            'language': language,
            'filtered_restaurants': restaurants
        }
        
        return context
    
    async def test_real_db_booking_flow(self):
        """Тест с реальной тестовой БД"""
        print("\n🗄️ ТЕСТ: Полный flow с тестовой БД")
        print("=" * 60)
        
        try:
            # Импортируем реальные модули после патча
            from src.bot.handlers.booking_handlers import (
                book_restaurant_callback, book_time_callback,
                book_guests_callback, book_date_callback
            )
            from src.bot.database.bookings import get_restaurant_working_hours
            
            # Подготовка
            restaurant = {
                'name': 'Test Italian Restaurant',
                'cuisine': 'Italian'
            }
            
            update = self.create_mock_update()
            context = self.create_mock_context([restaurant])
            
            # Патчим только translate_message, БД оставляем реальную
            with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
                mock_translate.side_effect = [
                    "What time should I book the table for?",
                    "For how many guests?",
                    "Are we booking for today?",
                    "Booking confirmed!",
                    "Instructions"
                ]
                
                print("1️⃣ Проверяем подключение к тестовой БД...")
                restaurant_data = await get_restaurant_working_hours('Test Italian Restaurant')
                if restaurant_data:
                    print(f"✅ Найден ресторан: {restaurant_data}")
                else:
                    print("❌ Ресторан не найден в тестовой БД")
                    return False
                
                print("2️⃣ Начинаем бронирование...")
                await book_restaurant_callback(update, context)
                
                booking_data = context.user_data.get('booking_data', {})
                if booking_data.get('restaurant') == restaurant:
                    print("✅ Ресторан выбран")
                else:
                    print("❌ Ошибка выбора ресторана")
                    return False
                
                print("3️⃣ Выбираем время (19:30)...")
                update.callback_query.data = "book_time_19:30"
                await book_time_callback(update, context)
                
                if booking_data.get('time') == time(19, 30):
                    print("✅ Время выбрано: 19:30")
                else:
                    print("❌ Ошибка выбора времени")
                    return False
                
                print("4️⃣ Выбираем гостей (2)...")
                update.callback_query.data = "book_guests_2"
                await book_guests_callback(update, context)
                
                if booking_data.get('guests') == 2:
                    print("✅ Гости выбраны: 2")
                else:
                    print("❌ Ошибка выбора гостей")
                    return False
                
                print("5️⃣ Выбираем дату (сегодня)...")
                update.callback_query.data = "book_date_today"
                await book_date_callback(update, context)
                
                # Проверяем что бронирование сохранено в реальной БД
                if context.user_data.get('current_booking_number'):
                    booking_number = context.user_data['current_booking_number']
                    print(f"✅ Бронирование сохранено в БД с номером: {booking_number}")
                    
                    # Проверяем что можем получить бронирование из БД
                    from src.bot.database.bookings import get_booking_by_number
                    saved_booking = await get_booking_by_number(booking_number)
                    
                    if saved_booking:
                        print(f"✅ Бронирование найдено в БД:")
                        print(f"   - Ресторан: {saved_booking['restaurant']}")
                        print(f"   - Время: {saved_booking['time']}")
                        print(f"   - Гости: {saved_booking['guests']}")
                        print(f"   - Статус: {saved_booking['status']}")
                        return True
                    else:
                        print("❌ Бронирование не найдено в БД")
                        return False
                else:
                    print("❌ Бронирование не сохранено")
                    return False
                    
        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_booking_preferences_with_db(self):
        """Тест добавления пожеланий с реальной БД"""
        print("\n💭 ТЕСТ: Пожелания с реальной БД")
        print("=" * 60)
        
        try:
            from src.bot.handlers.booking_handlers import handle_booking_preferences
            from src.bot.database.bookings import get_booking_by_number
            
            # Используем существующее тестовое бронирование
            existing_booking_number = 1  # Первое бронирование из тестовых данных
            
            update = self.create_mock_update()
            context = self.create_mock_context()
            
            context.user_data['current_booking_number'] = existing_booking_number
            update.message.text = "Столик у окна с видом на море"
            
            with patch('src.bot.handlers.booking_handlers.translate_message', new_callable=AsyncMock) as mock_translate:
                mock_translate.return_value = "Preferences saved"
                
                print(f"1️⃣ Добавляем пожелания к бронированию #{existing_booking_number}...")
                result = await handle_booking_preferences(update, context)
                
                if result:
                    print("✅ Пожелания обработаны")
                    
                    # Проверяем что пожелания сохранились в БД
                    updated_booking = await get_booking_by_number(existing_booking_number)
                    if updated_booking and "столик у окна" in updated_booking['preferences'].lower():
                        print("✅ Пожелания сохранены в БД")
                        return True
                    else:
                        print("❌ Пожелания не сохранились в БД")
                        return False
                else:
                    print("❌ Ошибка обработки пожеланий")
                    return False
                    
        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def check_test_db_status(self):
        """Проверяет статус тестовой БД"""
        print("\n📊 ПРОВЕРКА ТЕСТОВОЙ БД")
        print("=" * 40)
        
        try:
            from src.bot.database.test_connection import get_db_connection
            from psycopg2.extras import DictCursor
            
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=DictCursor)
            
            # Проверяем таблицы
            cur.execute("SELECT COUNT(*) FROM users")
            users_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM restaurants")
            restaurants_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM bookings")
            bookings_count = cur.fetchone()[0]
            
            cur.close()
            conn.close()
            
            print(f"✅ Тестовая БД доступна:")
            print(f"   - Пользователей: {users_count}")
            print(f"   - Ресторанов: {restaurants_count}")
            print(f"   - Бронирований: {bookings_count}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка доступа к тестовой БД: {e}")
            print("💡 Создайте тестовую БД: scripts/create_test_db.sh")
            return False
    
    async def run_all_tests(self):
        """Запуск всех тестов с тестовой БД"""
        print("🧪 FLOW ТЕСТ БРОНИРОВАНИЯ С ТЕСТОВОЙ БД")
        print("=" * 80)
        
        # Сначала проверяем БД
        if not await self.check_test_db_status():
            return
        
        tests = [
            ("real_db_flow", self.test_real_db_booking_flow),
            ("preferences_with_db", self.test_booking_preferences_with_db)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                success = await test_func()
                if success:
                    print(f"✅ {test_name}: ПРОЙДЕН")
                    passed += 1
                else:
                    print(f"❌ {test_name}: ПРОВАЛЕН")
                    failed += 1
            except Exception as e:
                print(f"💥 {test_name}: ОШИБКА - {e}")
                failed += 1
        
        print(f"\n📊 РЕЗУЛЬТАТЫ:")
        print(f"✅ Пройдено: {passed}")
        print(f"❌ Провалено: {failed}")
        print(f"🎯 Успешность: {passed/(passed+failed)*100:.1f}%")
        
        if passed == len(tests):
            print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ! Модуль работает с реальной БД.")
        else:
            print(f"\n⚠️ {failed} тестов провалено.")

async def main():
    """Главная функция"""
    tester = TestDBFlowTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 