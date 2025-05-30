"""
Integration тесты для полного цикла бронирования
"""
import pytest
import asyncio
from datetime import date, time, datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.bot.managers.booking_manager import BookingManager
from src.bot.handlers.booking_handlers import (
    book_restaurant_callback, book_restaurant_select_callback,
    book_time_callback, book_guests_callback, book_date_callback
)

class TestBookingIntegration:
    """Integration тесты для модуля бронирования"""
    
    @pytest.mark.asyncio
    async def test_full_booking_flow_single_restaurant(self):
        """Тест полного цикла бронирования с одним рестораном"""
        # Симулируем полный поток: кнопка РЕЗЕРВ -> время -> гости -> дата -> завершение
        
        update = Mock()
        context = Mock()
        query = Mock()
        
        # Настройка initial state
        update.callback_query = query
        update.effective_user.id = 12345
        update.effective_user.first_name = "John"
        update.effective_user.last_name = "Doe"
        update.effective_user.username = "johndoe"
        update.effective_chat = Mock()
        update.effective_chat.send_message = AsyncMock()
        
        restaurant = {
            'name': 'Test Restaurant',
            'cuisine': 'Italian',
            'working_hours': {'close': '23:00'}
        }
        
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': [restaurant]
        }
        
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        # Мокаем внешние зависимости
        with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
            with patch('src.bot.database.bookings.save_booking_to_db', new_callable=AsyncMock) as mock_save:
                with patch('src.bot.database.bookings.get_restaurant_working_hours', new_callable=AsyncMock) as mock_hours:
                    
                    mock_translate.side_effect = [
                        "What time should I book the table for?",
                        "For how many guests?", 
                        "Are we booking for today?",
                        "Booking confirmed!",
                        "Instructions"
                    ]
                    mock_save.return_value = 100
                    mock_hours.return_value = {'booking_contact': 'test_contact'}
                    
                    # Шаг 1: Нажатие кнопки РЕЗЕРВ
                    await book_restaurant_callback(update, context)
                    
                    # Проверяем что началось бронирование
                    assert 'booking_data' in context.user_data
                    booking_data = context.user_data['booking_data']
                    assert booking_data['restaurant'] == restaurant
                    assert booking_data['step'] == 'time_selection'
                    
                    # Шаг 2: Выбор времени (18:30)
                    query.data = "book_time_18:30"
                    await book_time_callback(update, context)
                    
                    assert booking_data['time'] == time(18, 30)
                    assert booking_data['step'] == 'guests_selection'
                    
                    # Шаг 3: Выбор количества гостей (2)
                    query.data = "book_guests_2"
                    await book_guests_callback(update, context)
                    
                    assert booking_data['guests'] == 2
                    assert booking_data['step'] == 'date_selection'
                    
                    # Шаг 4: Выбор даты (сегодня)
                    query.data = "book_date_today"
                    await book_date_callback(update, context)
                    
                    # Проверяем что бронирование завершено
                    mock_save.assert_called_once()
                    save_args = mock_save.call_args[1]
                    assert save_args['restaurant_name'] == 'Test Restaurant'
                    assert save_args['client_name'] == 'John Doe'
                    assert save_args['time'] == time(18, 30)
                    assert save_args['guests'] == 2
                    assert save_args['date_booking'] == date.today()
                    assert save_args['client_code'] == 12345
                    
                    # Проверяем что отправлены подтверждающие сообщения
                    assert update.effective_chat.send_message.call_count == 2
    
    @pytest.mark.asyncio  
    async def test_full_booking_flow_multiple_restaurants(self):
        """Тест полного цикла бронирования с выбором из нескольких ресторанов"""
        
        update = Mock()
        context = Mock()
        query = Mock()
        
        update.callback_query = query
        update.effective_user.id = 12345
        update.effective_user.first_name = "Jane"
        update.effective_user.last_name = "Smith"
        update.effective_chat = Mock()
        update.effective_chat.send_message = AsyncMock()
        
        restaurants = [
            {'name': 'Restaurant A', 'cuisine': 'Italian'},
            {'name': 'Restaurant B', 'cuisine': 'Thai'},
            {'name': 'Restaurant C', 'cuisine': 'French'}
        ]
        
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': restaurants
        }
        
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
            with patch('src.bot.database.bookings.save_booking_to_db', new_callable=AsyncMock) as mock_save:
                with patch('src.bot.database.bookings.get_restaurant_working_hours', new_callable=AsyncMock) as mock_hours:
                    
                    mock_translate.side_effect = [
                        "Which restaurant shall we book a table at?",
                        "What time should I book the table for?",
                        "For how many guests?",
                        "Are we booking for today?", 
                        "Booking confirmed!",
                        "Instructions"
                    ]
                    mock_save.return_value = 101
                    mock_hours.return_value = {'booking_contact': 'contact_b'}
                    
                    # Шаг 1: Нажатие кнопки РЕЗЕРВ (показывает выбор ресторана)
                    await book_restaurant_callback(update, context)
                    
                    assert context.user_data['booking_data']['step'] == 'restaurant_selection'
                    
                    # Шаг 2: Выбор второго ресторана (индекс 1)
                    query.data = "book_restaurant_1"
                    await book_restaurant_select_callback(update, context)
                    
                    booking_data = context.user_data['booking_data']
                    assert booking_data['restaurant'] == restaurants[1]  # Restaurant B
                    assert booking_data['step'] == 'time_selection'
                    
                    # Шаг 3: Выбор времени (19:00)
                    query.data = "book_time_19:00"
                    await book_time_callback(update, context)
                    
                    assert booking_data['time'] == time(19, 0)
                    
                    # Шаг 4: Выбор гостей (4)
                    query.data = "book_guests_4"
                    await book_guests_callback(update, context)
                    
                    assert booking_data['guests'] == 4
                    
                    # Шаг 5: Выбор даты (завтра)
                    query.data = "book_date_tomorrow"
                    await book_date_callback(update, context)
                    
                    # Проверяем итоговое бронирование
                    mock_save.assert_called_once()
                    save_args = mock_save.call_args[1]
                    assert save_args['restaurant_name'] == 'Restaurant B'
                    assert save_args['client_name'] == 'Jane Smith'
                    assert save_args['time'] == time(19, 0)
                    assert save_args['guests'] == 4
                    assert save_args['date_booking'] == date.today() + timedelta(days=1)
    
    @pytest.mark.asyncio
    async def test_booking_with_custom_time_and_date(self):
        """Тест бронирования с кастомным временем и датой"""
        
        update = Mock()
        context = Mock()
        query = Mock()
        
        update.callback_query = query
        update.effective_user.id = 12345
        update.effective_user.first_name = "Alex"
        update.effective_chat = Mock()
        update.effective_chat.send_message = AsyncMock()
        update.message = Mock()
        update.message.text = "20:15"
        update.message.reply_text = AsyncMock()
        
        restaurant = {'name': 'Custom Restaurant'}
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': [restaurant],
            'booking_data': {
                'user_id': 12345,
                'restaurant': restaurant,
                'step': 'time_selection'
            }
        }
        
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
            with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
                with patch('src.bot.database.bookings.save_booking_to_db', new_callable=AsyncMock) as mock_save:
                    
                    mock_translate.side_effect = [
                        "The restaurant is open until 11 PM. What time?",
                        "For how many guests?",
                        "Are we booking for today?",
                        "For which date should I book the table?",
                        "Booking confirmed!",
                        "Instructions"
                    ]
                    mock_ai.side_effect = ["20:15", "15.06.2024"]
                    mock_save.return_value = 102
                    
                    # Выбираем "ДРУГОЕ" для времени
                    query.data = "book_time_custom"
                    await book_time_callback(update, context)
                    
                    # Система должна ждать ввод кастомного времени
                    assert context.user_data['booking_data']['step'] == 'waiting_custom_time'
                    
                    # Вводим кастомное время
                    from src.bot.handlers.booking_handlers import handle_custom_time_input
                    result = await handle_custom_time_input(update, context)
                    
                    assert result is True
                    assert context.user_data['booking_data']['time'] == time(20, 15)
                    assert context.user_data['booking_data']['step'] == 'guests_selection'
                    
                    # Выбираем количество гостей
                    query.data = "book_guests_3"
                    await book_guests_callback(update, context)
                    
                    # Выбираем "ДРУГОЕ" для даты
                    query.data = "book_date_custom"
                    await book_date_callback(update, context)
                    
                    assert context.user_data['booking_data']['step'] == 'waiting_custom_date'
                    
                    # Вводим кастомную дату
                    update.message.text = "15 июня"
                    from src.bot.handlers.booking_handlers import handle_custom_date_input
                    result = await handle_custom_date_input(update, context)
                    
                    assert result is True
                    expected_date = datetime.strptime("15.06.2024", "%d.%m.%Y").date()
                    assert context.user_data['booking_data']['date'] == expected_date
                    
                    # Проверяем что бронирование сохранено
                    mock_save.assert_called_once()
                    save_args = mock_save.call_args[1]
                    assert save_args['time'] == time(20, 15)
                    assert save_args['guests'] == 3
                    assert save_args['date_booking'] == expected_date
    
    @pytest.mark.asyncio
    async def test_booking_with_preferences(self):
        """Тест добавления пожеланий после бронирования"""
        
        update = Mock()
        context = Mock()
        
        update.message = Mock()
        update.message.text = "Window table with sea view please"
        update.message.reply_text = AsyncMock()
        
        context.user_data = {
            'current_booking_number': 123,
            'language': 'en'
        }
        
        with patch('src.bot.handlers.booking_handlers.update_booking_preferences', new_callable=AsyncMock) as mock_update:
            with patch('src.bot.handlers.booking_handlers.translate_message', new_callable=AsyncMock) as mock_translate:
                
                mock_update.return_value = True
                mock_translate.return_value = "Your preferences have been saved"
                
                from src.bot.handlers.booking_handlers import handle_booking_preferences
                result = await handle_booking_preferences(update, context)
                
                assert result is True
                mock_update.assert_called_once_with(123, "Window table with sea view please")
                update.message.reply_text.assert_called_once()
                
                # Проверяем что номер бронирования очищен
                assert context.user_data['current_booking_number'] is None
    
    @pytest.mark.asyncio
    async def test_booking_from_chat_message(self):
        """Тест начала бронирования из сообщения в чате"""
        
        update = Mock()
        context = Mock()
        
        update.message = Mock()
        update.message.text = "I want to book a table at Blue Elephant"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 12345
        
        restaurants = [
            {'name': 'Blue Elephant', 'cuisine': 'Thai'},
            {'name': 'Red Tomato', 'cuisine': 'Italian'}
        ]
        
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': restaurants
        }
        
        with patch('src.bot.managers.booking_manager.ai_generate', new_callable=AsyncMock) as mock_ai:
            with patch.object(BookingManager, '_ask_for_time', new_callable=AsyncMock) as mock_ask_time:
                
                mock_ai.return_value = "Blue Elephant"
                
                await BookingManager.start_booking_from_chat(update, context, update.message.text)
                
                # Проверяем что система определила ресторан и начала бронирование
                assert 'booking_data' in context.user_data
                booking_data = context.user_data['booking_data']
                assert booking_data['restaurant']['name'] == 'Blue Elephant'
                assert booking_data['step'] == 'time_selection'
                
                mock_ask_time.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_booking_error_handling(self):
        """Тест обработки ошибок в процессе бронирования"""
        
        update = Mock()
        context = Mock()
        query = Mock()
        
        update.callback_query = query
        update.effective_user.id = 12345
        update.effective_chat = Mock()
        update.effective_chat.send_message = AsyncMock()
        
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': []  # Пустой список ресторанов
        }
        
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
            mock_translate.return_value = "No restaurants found"
            
            await book_restaurant_callback(update, context)
            
            # Проверяем что система корректно обработала отсутствие ресторанов
            query.edit_message_text.assert_called_once_with("No restaurants found")
    
    @pytest.mark.asyncio
    async def test_booking_database_error(self):
        """Тест обработки ошибки базы данных при сохранении"""
        
        update = Mock()
        context = Mock()
        
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "Test"
        update.effective_user.last_name = "User"
        update.effective_chat = Mock()
        update.effective_chat.send_message = AsyncMock()
        
        restaurant = {'name': 'Test Restaurant'}
        context.user_data = {
            'language': 'en',
            'booking_data': {
                'restaurant': restaurant,
                'time': time(19, 0),
                'guests': 2,
                'date': date.today()
            }
        }
        
        with patch('src.bot.database.bookings.save_booking_to_db', new_callable=AsyncMock) as mock_save:
            with patch('src.bot.database.bookings.get_restaurant_working_hours', new_callable=AsyncMock) as mock_hours:
                
                mock_save.return_value = None  # Симулируем ошибку базы данных
                mock_hours.return_value = {'booking_contact': 'test'}
                
                await BookingManager._complete_booking(update, context)
                
                # Проверяем что отправлено сообщение об ошибке
                update.effective_chat.send_message.assert_called_once_with(
                    "Ошибка при сохранении бронирования. Попробуйте позже."
                ) 