"""
Unit тесты для модуля бронирования
"""
import pytest
import asyncio
from datetime import date, time, datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.bot.managers.booking_manager import BookingManager
from src.bot.handlers.booking_handlers import (
    handle_custom_time_input, handle_custom_date_input, handle_booking_preferences
)

class TestBookingManager:
    """Тесты для BookingManager"""
    
    @pytest.mark.asyncio
    async def test_start_booking_single_restaurant(self):
        """Тест начала бронирования с одним рестораном"""
        update = Mock()
        context = Mock()
        query = Mock()
        
        update.callback_query = query
        update.effective_user.id = 12345
        
        # Мокаем данные
        restaurant = {'name': 'Test Restaurant', 'cuisine': 'Italian'}
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': [restaurant]
        }
        
        query.answer = AsyncMock()
        
        with patch.object(BookingManager, '_ask_for_time', new_callable=AsyncMock) as mock_ask_time:
            await BookingManager.start_booking_from_button(update, context)
            
            # Проверяем что данные бронирования инициализированы
            assert 'booking_data' in context.user_data
            booking_data = context.user_data['booking_data']
            assert booking_data['user_id'] == 12345
            assert booking_data['restaurant'] == restaurant
            assert booking_data['step'] == 'time_selection'
            
            # Проверяем что был вызван метод выбора времени
            mock_ask_time.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_booking_multiple_restaurants(self):
        """Тест начала бронирования с несколькими ресторанами"""
        update = Mock()
        context = Mock()
        query = Mock()
        
        update.callback_query = query
        update.effective_user.id = 12345
        
        # Мокаем данные с несколькими ресторанами
        restaurants = [
            {'name': 'Restaurant 1', 'cuisine': 'Italian'},
            {'name': 'Restaurant 2', 'cuisine': 'Thai'}
        ]
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': restaurants
        }
        
        query.answer = AsyncMock()
        
        with patch.object(BookingManager, '_ask_which_restaurant', new_callable=AsyncMock) as mock_ask_restaurant:
            await BookingManager.start_booking_from_button(update, context)
            
            # Проверяем что данные бронирования инициализированы
            assert 'booking_data' in context.user_data
            booking_data = context.user_data['booking_data']
            assert booking_data['user_id'] == 12345
            assert booking_data['restaurants'] == restaurants
            assert booking_data['step'] == 'restaurant_selection'
            
            # Проверяем что был вызван метод выбора ресторана
            mock_ask_restaurant.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ask_for_time_generation(self):
        """Тест генерации вариантов времени"""
        update = Mock()
        context = Mock()
        restaurant = {'name': 'Test Restaurant'}
        
        context.user_data = {'language': 'en'}
        
        # Мокаем translate_message
        with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
            mock_translate.return_value = "What time should I book the table for?"
            
            # Мокаем update для проверки отправки сообщения
            update.callback_query = Mock()
            update.callback_query.edit_message_text = AsyncMock()
            
            await BookingManager._ask_for_time(update, context, restaurant)
            
            # Проверяем что сообщение было отправлено с правильными кнопками
            mock_translate.assert_called_once_with('booking_time_question', 'en')
            update.callback_query.edit_message_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_restaurant_from_message(self):
        """Тест извлечения ресторана из сообщения"""
        restaurants = [
            {'name': 'Blue Elephant'},
            {'name': 'Acqua Restaurant'}
        ]
        
        with patch('src.bot.managers.booking_manager.ai_generate', new_callable=AsyncMock) as mock_ai:
            # Тест успешного извлечения
            mock_ai.return_value = "Blue Elephant"
            result = await BookingManager._extract_restaurant_from_message(
                "I want to book Blue Elephant", restaurants, 'en'
            )
            assert result == "Blue Elephant"
            
            # Тест неудачного извлечения
            mock_ai.return_value = "UNKNOWN"
            result = await BookingManager._extract_restaurant_from_message(
                "I want to book", restaurants, 'en'
            )
            assert result is None

class TestBookingHandlers:
    """Тесты для обработчиков бронирования"""
    
    @pytest.mark.asyncio
    async def test_handle_custom_time_input_success(self):
        """Тест успешной обработки кастомного времени"""
        update = Mock()
        context = Mock()
        
        # Настраиваем контекст
        context.user_data = {
            'booking_data': {'step': 'waiting_custom_time'},
            'language': 'en'
        }
        
        update.message.text = "19:30"
        update.message.reply_text = AsyncMock()
        
        with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
            with patch.object(BookingManager, '_ask_for_guests', new_callable=AsyncMock) as mock_ask_guests:
                mock_ai.return_value = "19:30"
                
                result = await handle_custom_time_input(update, context)
                
                assert result is True
                assert 'time' in context.user_data['booking_data']
                assert context.user_data['booking_data']['step'] == 'guests_selection'
                mock_ask_guests.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_custom_time_input_invalid(self):
        """Тест обработки неверного времени"""
        update = Mock()
        context = Mock()
        
        context.user_data = {
            'booking_data': {'step': 'waiting_custom_time'},
            'language': 'en'
        }
        
        update.message.text = "invalid time"
        update.message.reply_text = AsyncMock()
        
        with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
            with patch('src.bot.handlers.booking_handlers.translate_message', new_callable=AsyncMock) as mock_translate:
                mock_ai.return_value = "INVALID"
                mock_translate.return_value = "Invalid time format"
                
                result = await handle_custom_time_input(update, context)
                
                assert result is True
                update.message.reply_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_custom_date_input_success(self):
        """Тест успешной обработки кастомной даты"""
        update = Mock()
        context = Mock()
        
        context.user_data = {
            'booking_data': {'step': 'waiting_custom_date'},
            'language': 'en'
        }
        
        tomorrow = date.today() + timedelta(days=1)
        update.message.text = "tomorrow"
        
        with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
            with patch.object(BookingManager, '_complete_booking', new_callable=AsyncMock) as mock_complete:
                mock_ai.return_value = tomorrow.strftime('%d.%m.%Y')
                
                result = await handle_custom_date_input(update, context)
                
                assert result is True
                assert 'date' in context.user_data['booking_data']
                assert context.user_data['booking_data']['date'] == tomorrow
                mock_complete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_booking_preferences(self):
        """Тест обработки дополнительных пожеланий"""
        update = Mock()
        context = Mock()
        
        context.user_data = {'current_booking_number': 123, 'language': 'en'}
        update.message.text = "Window table please"
        update.message.reply_text = AsyncMock()
        
        with patch('src.bot.handlers.booking_handlers.update_booking_preferences', new_callable=AsyncMock) as mock_update:
            with patch('src.bot.handlers.booking_handlers.translate_message', new_callable=AsyncMock) as mock_translate:
                mock_update.return_value = True
                mock_translate.return_value = "Preferences saved"
                
                result = await handle_booking_preferences(update, context)
                
                assert result is True
                mock_update.assert_called_once_with(123, "Window table please")
                update.message.reply_text.assert_called_once()
                assert context.user_data['current_booking_number'] is None
    
    @pytest.mark.asyncio
    async def test_handle_booking_preferences_no_booking(self):
        """Тест обработки пожеланий без активного бронирования"""
        update = Mock()
        context = Mock()
        
        context.user_data = {}  # Нет current_booking_number
        
        result = await handle_booking_preferences(update, context)
        
        assert result is False

class TestBookingFlow:
    """Интеграционные тесты полного flow бронирования"""
    
    @pytest.mark.asyncio
    async def test_complete_booking_flow_single_restaurant(self):
        """Тест полного flow бронирования с одним рестораном"""
        update = Mock()
        context = Mock()
        
        # Инициализируем данные как в реальном сценарии
        restaurant = {
            'name': 'Test Restaurant',
            'cuisine': 'Italian',
            'booking_contact': 'test_contact'
        }
        
        context.user_data = {
            'language': 'en',
            'filtered_restaurants': [restaurant],
            'booking_data': {
                'user_id': 12345,
                'restaurant': restaurant,
                'time': time(19, 30),
                'guests': 2,
                'date': date.today(),
                'step': 'completion'
            }
        }
        
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "John"
        update.effective_user.last_name = "Doe"
        update.effective_user.username = "johndoe"
        
        update.effective_chat = Mock()
        update.effective_chat.send_message = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.save_booking_to_db', new_callable=AsyncMock) as mock_save:
            with patch('src.bot.managers.booking_manager.get_restaurant_working_hours', new_callable=AsyncMock) as mock_hours:
                with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
                    mock_save.return_value = 100  # booking_number
                    mock_hours.return_value = {'booking_contact': 'test_contact'}
                    mock_translate.side_effect = ["Booking confirmed!", "Instructions"]
                    
                    await BookingManager._complete_booking(update, context)
                    
                    # Проверяем что бронирование было сохранено
                    mock_save.assert_called_once()
                    save_args = mock_save.call_args[1]
                    assert save_args['restaurant_name'] == 'Test Restaurant'
                    assert save_args['client_name'] == 'John Doe'
                    assert save_args['guests'] == 2
                    assert save_args['client_code'] == 12345
                    
                    # Проверяем что сообщения были отправлены
                    assert update.effective_chat.send_message.call_count == 2
                    
                    # Проверяем что номер бронирования сохранен
                    assert context.user_data['current_booking_number'] == 100
    
    @pytest.mark.asyncio
    async def test_booking_flow_with_custom_inputs(self):
        """Тест flow с кастомными вводами времени и даты"""
        # Этот тест проверяет что система может обработать
        # нестандартные форматы времени и даты через AI
        
        # Тест кастомного времени
        update = Mock()
        context = Mock()
        
        context.user_data = {
            'booking_data': {'step': 'waiting_custom_time'},
            'language': 'en'
        }
        update.message.text = "half past seven in the evening"
        
        with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = "19:30"
            
            result = await handle_custom_time_input(update, context)
            
            assert result is True
            assert context.user_data['booking_data']['time'] == time(19, 30)
        
        # Тест кастомной даты
        context.user_data = {
            'booking_data': {'step': 'waiting_custom_date'},
            'language': 'en'
        }
        update.message.text = "next Friday"
        
        next_week = date.today() + timedelta(days=7)
        with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = next_week.strftime('%d.%m.%Y')
            
            result = await handle_custom_date_input(update, context)
            
            assert result is True
            assert context.user_data['booking_data']['date'] == next_week 