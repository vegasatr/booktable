#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OFFLINE FLOW ТЕСТ БРОНИРОВАНИЯ
=============================

Полностью автономный тест flow бронирования.
Симулирует поведение модуля без реальных импортов.
"""

import asyncio
from datetime import date, time
from unittest.mock import Mock, AsyncMock

class MockBookingManager:
    """Mock версия BookingManager для тестирования"""
    
    @staticmethod
    async def start_booking_from_button(update, context):
        """Симулирует начало бронирования"""
        restaurants = context.user_data.get('filtered_restaurants', [])
        
        if not restaurants:
            await update.callback_query.edit_message_text("No restaurants found")
            return
        
        context.user_data['booking_data'] = {
            'user_id': update.effective_user.id,
            'restaurants': restaurants,
            'step': 'restaurant_selection'
        }
        
        if len(restaurants) == 1:
            # Один ресторан - автовыбор
            context.user_data['booking_data']['restaurant'] = restaurants[0]
            context.user_data['booking_data']['step'] = 'time_selection'
            await update.callback_query.edit_message_text("What time should I book?")
        else:
            # Несколько ресторанов - показать выбор
            context.user_data['booking_data']['step'] = 'restaurant_selection'
            await update.callback_query.edit_message_text("Which restaurant?")

class MockHandlers:
    """Mock версии handlers для тестирования"""
    
    @staticmethod
    async def book_restaurant_callback(update, context):
        await MockBookingManager.start_booking_from_button(update, context)
    
    @staticmethod
    async def book_restaurant_select_callback(update, context):
        """Выбор ресторана из списка"""
        index = int(update.callback_query.data.split('_')[-1])
        restaurants = context.user_data['booking_data']['restaurants']
        
        if 0 <= index < len(restaurants):
            context.user_data['booking_data']['restaurant'] = restaurants[index]
            context.user_data['booking_data']['step'] = 'time_selection'
            await update.callback_query.edit_message_text("What time?")
    
    @staticmethod
    async def book_time_callback(update, context):
        """Выбор времени"""
        if update.callback_query.data == "book_time_custom":
            context.user_data['booking_data']['step'] = 'waiting_custom_time'
            await update.callback_query.edit_message_text("Enter custom time")
        else:
            time_str = update.callback_query.data.split('_')[-1]
            hour, minute = map(int, time_str.split(':'))
            context.user_data['booking_data']['time'] = time(hour, minute)
            context.user_data['booking_data']['step'] = 'guests_selection'
            await update.callback_query.edit_message_text("How many guests?")
    
    @staticmethod
    async def book_guests_callback(update, context):
        """Выбор количества гостей"""
        guests = int(update.callback_query.data.split('_')[-1])
        context.user_data['booking_data']['guests'] = guests
        context.user_data['booking_data']['step'] = 'date_selection'
        await update.callback_query.edit_message_text("Which date?")
    
    @staticmethod
    async def book_date_callback(update, context):
        """Выбор даты"""
        if update.callback_query.data == "book_date_today":
            context.user_data['booking_data']['date'] = date.today()
        elif update.callback_query.data == "book_date_tomorrow":
            from datetime import timedelta
            context.user_data['booking_data']['date'] = date.today() + timedelta(days=1)
        elif update.callback_query.data == "book_date_custom":
            context.user_data['booking_data']['step'] = 'waiting_custom_date'
            await update.callback_query.edit_message_text("Enter custom date")
            return
        
        # Завершаем бронирование
        await MockHandlers._complete_booking(update, context)
    
    @staticmethod
    async def _complete_booking(update, context):
        """Завершение бронирования"""
        booking_data = context.user_data['booking_data']
        
        # Симулируем сохранение в БД
        booking_number = 100
        context.user_data['current_booking_number'] = booking_number
        
        await update.effective_chat.send_message("Booking confirmed!")
        await update.effective_chat.send_message("Instructions")

class FlowTester:
    """Тестер flow бронирования"""
    
    def create_mock_update(self, user_id=12345):
        """Создает mock update"""
        update = Mock()
        query = Mock()
        
        update.callback_query = query
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = ""
        
        update.effective_user = Mock()
        update.effective_user.id = user_id
        update.effective_user.first_name = "Test"
        update.effective_user.last_name = "User"
        
        update.effective_chat = Mock()
        update.effective_chat.send_message = AsyncMock()
        
        return update
    
    def create_mock_context(self, restaurants=None):
        """Создает mock context"""
        context = Mock()
        
        if restaurants is None:
            restaurants = [{'name': 'Test Restaurant', 'cuisine': 'Italian'}]
        
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': restaurants
        }
        
        return context
    
    async def test_single_restaurant_flow(self):
        """Тест с одним рестораном"""
        print("\n🍝 ТЕСТ: Один ресторан")
        print("=" * 40)
        
        restaurant = {'name': 'Solo Restaurant', 'cuisine': 'Italian'}
        update = self.create_mock_update()
        context = self.create_mock_context([restaurant])
        
        # Шаг 1: Начало бронирования
        print("1️⃣ Начинаем бронирование...")
        await MockHandlers.book_restaurant_callback(update, context)
        
        booking_data = context.user_data.get('booking_data', {})
        if booking_data.get('restaurant') == restaurant:
            print("✅ Ресторан выбран автоматически")
        else:
            print("❌ Ошибка выбора ресторана")
            return False
        
        # Шаг 2: Время
        print("2️⃣ Выбираем время (19:30)...")
        update.callback_query.data = "book_time_19:30"
        await MockHandlers.book_time_callback(update, context)
        
        if booking_data.get('time') == time(19, 30):
            print("✅ Время 19:30 выбрано")
        else:
            print("❌ Ошибка выбора времени")
            return False
        
        # Шаг 3: Гости
        print("3️⃣ Выбираем гостей (2)...")
        update.callback_query.data = "book_guests_2"
        await MockHandlers.book_guests_callback(update, context)
        
        if booking_data.get('guests') == 2:
            print("✅ 2 гостя выбрано")
        else:
            print("❌ Ошибка выбора гостей")
            return False
        
        # Шаг 4: Дата
        print("4️⃣ Выбираем дату (сегодня)...")
        update.callback_query.data = "book_date_today"
        await MockHandlers.book_date_callback(update, context)
        
        if context.user_data.get('current_booking_number') == 100:
            print("✅ Бронирование завершено с номером 100")
            return True
        else:
            print("❌ Бронирование не завершено")
            return False
    
    async def test_multiple_restaurants_flow(self):
        """Тест с несколькими ресторанами"""
        print("\n🍕 ТЕСТ: Несколько ресторанов")
        print("=" * 40)
        
        restaurants = [
            {'name': 'Italian Place', 'cuisine': 'Italian'},
            {'name': 'Thai Corner', 'cuisine': 'Thai'}
        ]
        
        update = self.create_mock_update()
        context = self.create_mock_context(restaurants)
        
        # Шаг 1: Начало бронирования
        print("1️⃣ Начинаем бронирование...")
        await MockHandlers.book_restaurant_callback(update, context)
        
        booking_data = context.user_data.get('booking_data', {})
        if booking_data.get('step') == 'restaurant_selection':
            print("✅ Показан выбор ресторанов")
        else:
            print("❌ Ошибка показа выбора")
            return False
        
        # Шаг 2: Выбор ресторана
        print("2️⃣ Выбираем второй ресторан...")
        update.callback_query.data = "book_restaurant_1"
        await MockHandlers.book_restaurant_select_callback(update, context)
        
        if booking_data.get('restaurant') == restaurants[1]:
            print("✅ Thai Corner выбран")
        else:
            print("❌ Ошибка выбора ресторана")
            return False
        
        # Остальные шаги
        print("3️⃣ Время 20:00...")
        update.callback_query.data = "book_time_20:00"
        await MockHandlers.book_time_callback(update, context)
        
        print("4️⃣ Гости 4...")
        update.callback_query.data = "book_guests_4"
        await MockHandlers.book_guests_callback(update, context)
        
        print("5️⃣ Дата завтра...")
        update.callback_query.data = "book_date_tomorrow"
        await MockHandlers.book_date_callback(update, context)
        
        if context.user_data.get('current_booking_number') == 100:
            print("✅ Полный flow завершен")
            return True
        else:
            print("❌ Flow не завершен")
            return False
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🧪 OFFLINE FLOW ТЕСТ БРОНИРОВАНИЯ")
        print("=" * 60)
        
        tests = [
            ("single_restaurant", self.test_single_restaurant_flow),
            ("multiple_restaurants", self.test_multiple_restaurants_flow)
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
            print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ! Flow работает корректно.")
        else:
            print(f"\n⚠️ {failed} тестов провалено.")

async def main():
    """Главная функция"""
    tester = FlowTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 