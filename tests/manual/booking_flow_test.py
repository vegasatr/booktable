#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
РУЧНОЙ FLOW ТЕСТ БРОНИРОВАНИЯ
============================

Этот модуль тестирует полный цикл бронирования столиков в ресторанах.
Симулирует реальное взаимодействие пользователя с ботом через Telegram.

Тестирует:
- Два способа начала бронирования (кнопка РЕЗЕРВ + чат)
- Полный flow: ресторан → время → гости → дата → подтверждение
- Обработку кастомных вводов (время, дата)
- Добавление пожеланий после бронирования

ЗАПУСК: python tests/manual/booking_flow_test.py
"""

import sys
import os
import asyncio
import json
from datetime import date, time, datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# Добавляем корень проекта в PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.bot.managers.booking_manager import BookingManager
from src.bot.handlers.booking_handlers import (
    book_restaurant_callback, book_restaurant_select_callback,
    book_time_callback, book_guests_callback, book_date_callback,
    handle_custom_time_input, handle_custom_date_input, handle_booking_preferences
)

class BookingFlowTester:
    """Класс для тестирования flow бронирования"""
    
    def __init__(self):
        self.test_results = []
        self.current_context = {}
        
    def create_mock_update(self, user_id=12345, username="testuser", 
                          first_name="Test", last_name="User"):
        """Создает mock объект update для тестирования"""
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
        """Создает mock объект context с тестовыми данными"""
        context = Mock()
        
        # Дефолтные рестораны для тестирования
        if restaurants is None:
            restaurants = [
                {
                    'name': 'Test Italian Restaurant',
                    'cuisine': 'Italian',
                    'working_hours': {'close': '23:00'}
                },
                {
                    'name': 'Test Thai Restaurant', 
                    'cuisine': 'Thai',
                    'working_hours': {'close': '22:00'}
                }
            ]
        
        context.user_data = {
            'language': language,
            'filtered_restaurants': restaurants
        }
        
        return context
    
    async def test_single_restaurant_flow(self):
        """Тест полного flow с одним рестораном"""
        print("\n🍝 ТЕСТ: Бронирование с одним рестораном")
        print("=" * 60)
        
        try:
            # Подготовка
            restaurant = {
                'name': 'Solo Restaurant',
                'cuisine': 'Italian',
                'working_hours': {'close': '23:00'}
            }
            
            update = self.create_mock_update()
            context = self.create_mock_context([restaurant])
            
            with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
                with patch('src.bot.database.bookings.save_booking_to_db', new_callable=AsyncMock) as mock_save:
                    with patch('src.bot.database.bookings.get_restaurant_working_hours', new_callable=AsyncMock) as mock_hours:
                        
                        # Настройка моков
                        mock_translate.side_effect = [
                            "What time should I book the table for?",
                            "For how many guests?",
                            "Are we booking for today?",
                            "Booking confirmed!",
                            "Instructions"
                        ]
                        mock_save.return_value = 100
                        mock_hours.return_value = {'booking_contact': '@test_restaurant'}
                        
                        print("1️⃣ Начинаем бронирование (кнопка РЕЗЕРВ)")
                        await book_restaurant_callback(update, context)
                        
                        # Проверяем что началось бронирование
                        booking_data = context.user_data.get('booking_data', {})
                        if booking_data.get('restaurant') == restaurant:
                            print("✅ Ресторан выбран автоматически")
                        else:
                            print("❌ Ошибка выбора ресторана")
                            return False
                        
                        print("2️⃣ Выбираем время (19:30)")
                        update.callback_query.data = "book_time_19:30"
                        await book_time_callback(update, context)
                        
                        if booking_data.get('time') == time(19, 30):
                            print("✅ Время выбрано: 19:30")
                        else:
                            print("❌ Ошибка выбора времени")
                            return False
                        
                        print("3️⃣ Выбираем количество гостей (2)")
                        update.callback_query.data = "book_guests_2"
                        await book_guests_callback(update, context)
                        
                        if booking_data.get('guests') == 2:
                            print("✅ Гости выбраны: 2")
                        else:
                            print("❌ Ошибка выбора гостей")
                            return False
                        
                        print("4️⃣ Выбираем дату (сегодня)")
                        update.callback_query.data = "book_date_today"
                        await book_date_callback(update, context)
                        
                        # Проверяем что бронирование завершено
                        if mock_save.called:
                            save_args = mock_save.call_args[1]
                            print(f"✅ Бронирование сохранено:")
                            print(f"   - Ресторан: {save_args['restaurant_name']}")
                            print(f"   - Клиент: {save_args['client_name']}")
                            print(f"   - Время: {save_args['time']}")
                            print(f"   - Дата: {save_args['date_booking']}")
                            print(f"   - Гости: {save_args['guests']}")
                            return True
                        else:
                            print("❌ Бронирование не сохранено")
                            return False
                            
        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            return False
    
    async def test_multiple_restaurants_flow(self):
        """Тест flow с выбором из нескольких ресторанов"""
        print("\n🍕 ТЕСТ: Выбор из нескольких ресторанов")
        print("=" * 60)
        
        try:
            restaurants = [
                {'name': 'Italian Place', 'cuisine': 'Italian'},
                {'name': 'Thai Corner', 'cuisine': 'Thai'},
                {'name': 'French Bistro', 'cuisine': 'French'}
            ]
            
            update = self.create_mock_update()
            context = self.create_mock_context(restaurants)
            
            with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
                with patch('src.bot.database.bookings.save_booking_to_db', new_callable=AsyncMock) as mock_save:
                    
                    mock_translate.side_effect = [
                        "Which restaurant shall we book a table at?",
                        "What time should I book the table for?",
                        "For how many guests?",
                        "Are we booking for today?",
                        "Booking confirmed!",
                        "Instructions"
                    ]
                    mock_save.return_value = 101
                    
                    print("1️⃣ Начинаем бронирование (показывается выбор ресторанов)")
                    await book_restaurant_callback(update, context)
                    
                    booking_data = context.user_data.get('booking_data', {})
                    if booking_data.get('step') == 'restaurant_selection':
                        print("✅ Показан выбор ресторанов")
                    else:
                        print("❌ Ошибка в показе выбора")
                        return False
                    
                    print("2️⃣ Выбираем второй ресторан (Thai Corner)")
                    update.callback_query.data = "book_restaurant_1"  # Индекс 1
                    await book_restaurant_select_callback(update, context)
                    
                    if booking_data.get('restaurant') == restaurants[1]:
                        print("✅ Выбран Thai Corner")
                    else:
                        print("❌ Ошибка выбора ресторана")
                        return False
                    
                    print("3️⃣ Далее выбираем время (20:00)")
                    update.callback_query.data = "book_time_20:00"
                    await book_time_callback(update, context)
                    
                    print("4️⃣ Выбираем гостей (4)")
                    update.callback_query.data = "book_guests_4"
                    await book_guests_callback(update, context)
                    
                    print("5️⃣ Выбираем дату (завтра)")
                    update.callback_query.data = "book_date_tomorrow"
                    await book_date_callback(update, context)
                    
                    if mock_save.called:
                        save_args = mock_save.call_args[1]
                        if save_args['restaurant_name'] == 'Thai Corner':
                            print("✅ Правильный ресторан забронирован")
                            return True
                    
                    print("❌ Проблема с финальным бронированием")
                    return False
                    
        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            return False
    
    async def test_custom_time_and_date(self):
        """Тест кастомного времени и даты"""
        print("\n🕐 ТЕСТ: Кастомное время и дата")
        print("=" * 60)
        
        try:
            restaurant = {'name': 'Custom Restaurant', 'cuisine': 'Any'}
            update = self.create_mock_update()
            context = self.create_mock_context([restaurant])
            
            # Начальное состояние для кастомного времени
            context.user_data['booking_data'] = {
                'restaurant': restaurant,
                'step': 'waiting_custom_time'
            }
            
            with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
                with patch.object(BookingManager, '_ask_for_guests', new_callable=AsyncMock):
                    
                    print("1️⃣ Вводим кастомное время: 'половина восьмого вечера'")
                    update.message.text = "половина восьмого вечера"
                    mock_ai.return_value = "19:30"
                    
                    result = await handle_custom_time_input(update, context)
                    
                    if result and context.user_data['booking_data'].get('time') == time(19, 30):
                        print("✅ AI распарсил время: 19:30")
                    else:
                        print("❌ Ошибка парсинга времени")
                        return False
            
            # Тест кастомной даты
            context.user_data['booking_data']['step'] = 'waiting_custom_date'
            
            with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
                with patch.object(BookingManager, '_complete_booking', new_callable=AsyncMock):
                    
                    print("2️⃣ Вводим кастомную дату: 'следующая пятница'")
                    next_friday = date.today() + timedelta(days=7)
                    update.message.text = "следующая пятница"
                    mock_ai.return_value = next_friday.strftime('%d.%m.%Y')
                    
                    result = await handle_custom_date_input(update, context)
                    
                    if result and context.user_data['booking_data'].get('date') == next_friday:
                        print(f"✅ AI распарсил дату: {next_friday}")
                        return True
                    else:
                        print("❌ Ошибка парсинга даты")
                        return False
                        
        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            return False
    
    async def test_booking_preferences(self):
        """Тест добавления пожеланий после бронирования"""
        print("\n💭 ТЕСТ: Дополнительные пожелания")
        print("=" * 60)
        
        try:
            update = self.create_mock_update()
            context = self.create_mock_context()
            
            # Симулируем состояние после завершения бронирования
            context.user_data['current_booking_number'] = 123
            update.message.text = "Столик у окна с видом на море, пожалуйста"
            
            with patch('src.bot.database.bookings.update_booking_preferences', new_callable=AsyncMock) as mock_update:
                with patch('src.bot.handlers.booking_handlers.translate_message', new_callable=AsyncMock) as mock_translate:
                    
                    mock_update.return_value = True
                    mock_translate.return_value = "Your preferences have been saved"
                    
                    print("1️⃣ Добавляем пожелание: 'Столик у окна с видом на море'")
                    result = await handle_booking_preferences(update, context)
                    
                    if result and mock_update.called:
                        call_args = mock_update.call_args[0]
                        if call_args[0] == 123 and "столик у окна" in call_args[1].lower():
                            print("✅ Пожелания сохранены для бронирования #123")
                            
                            # Проверяем что номер бронирования очищен
                            if context.user_data.get('current_booking_number') is None:
                                print("✅ Номер бронирования очищен")
                                return True
                            else:
                                print("⚠️ Номер бронирования не очищен")
                                return False
                        else:
                            print("❌ Неправильные параметры при сохранении")
                            return False
                    else:
                        print("❌ Пожелания не сохранены")
                        return False
                        
        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            return False
    
    async def test_booking_from_chat(self):
        """Тест начала бронирования из сообщения в чате"""
        print("\n💬 ТЕСТ: Бронирование из чата")
        print("=" * 60)
        
        try:
            restaurants = [
                {'name': 'Blue Elephant', 'cuisine': 'Thai'},
                {'name': 'Red Dragon', 'cuisine': 'Chinese'}
            ]
            
            update = self.create_mock_update()
            context = self.create_mock_context(restaurants)
            
            with patch('src.bot.managers.booking_manager.ai_generate', new_callable=AsyncMock) as mock_ai:
                with patch.object(BookingManager, '_ask_for_time', new_callable=AsyncMock) as mock_ask_time:
                    
                    print("1️⃣ Сообщение: 'хочу забронировать столик в Blue Elephant'")
                    message_text = "хочу забронировать столик в Blue Elephant"
                    mock_ai.return_value = "Blue Elephant"
                    
                    await BookingManager.start_booking_from_chat(update, context, message_text)
                    
                    booking_data = context.user_data.get('booking_data', {})
                    if booking_data.get('restaurant', {}).get('name') == 'Blue Elephant':
                        print("✅ AI определил ресторан из сообщения")
                        
                        if mock_ask_time.called:
                            print("✅ Начат процесс выбора времени")
                            return True
                        else:
                            print("❌ Не начат процесс выбора времени")
                            return False
                    else:
                        print("❌ AI не смог определить ресторан")
                        return False
                        
        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            return False
    
    async def run_all_tests(self):
        """Запускает все тесты flow бронирования"""
        print("🧪 РУЧНОЙ FLOW ТЕСТ БРОНИРОВАНИЯ")
        print("=" * 80)
        
        tests = [
            ("single_restaurant", self.test_single_restaurant_flow),
            ("multiple_restaurants", self.test_multiple_restaurants_flow),
            ("custom_inputs", self.test_custom_time_and_date),
            ("preferences", self.test_booking_preferences),
            ("chat_booking", self.test_booking_from_chat)
        ]
        
        results = {"passed": 0, "failed": 0}
        
        for test_name, test_func in tests:
            try:
                success = await test_func()
                if success:
                    print(f"✅ {test_name.replace('_', ' ').title()}: ПРОЙДЕН")
                    results["passed"] += 1
                else:
                    print(f"❌ {test_name.replace('_', ' ').title()}: ПРОВАЛЕН")
                    results["failed"] += 1
            except Exception as e:
                print(f"💥 {test_name.replace('_', ' ').title()}: ОШИБКА - {e}")
                results["failed"] += 1
        
        print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"✅ Пройдено: {results['passed']}")
        print(f"❌ Провалено: {results['failed']}")
        print(f"🎯 Успешность: {results['passed']/(results['passed']+results['failed'])*100:.1f}%")
        
        if results["passed"] == len(tests):
            print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ! Модуль бронирования работает корректно.")
        else:
            print(f"\n⚠️ {results['failed']} тестов провалено. Требуется доработка.")

async def main():
    """Главная функция запуска тестов"""
    tester = BookingFlowTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 