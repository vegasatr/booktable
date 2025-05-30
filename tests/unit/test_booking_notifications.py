"""
Unit тесты для уведомлений при бронировании
"""
import pytest
import asyncio
from datetime import date, time as datetime_time
from unittest.mock import Mock, patch, AsyncMock

from src.bot.managers.booking_manager import BookingManager

class TestBookingNotifications:
    """Тесты уведомлений ресторанов при бронировании"""
    
    @pytest.mark.asyncio
    async def test_notify_restaurant_with_equals_prefix(self):
        """Тест очистки символа = в начале контакта"""
        
        # Подготовка данных
        booking_number = 42
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(19, 30),
            'guests': 2
        }
        
        user = Mock()
        user.first_name = "John"
        user.last_name = "Doe"
        user.username = "johndoe"
        user.id = 12345
        
        restaurant_contact = "=+79219129292"  # Контакт с символом =
        
        # Мокаем Bot
        with patch('src.bot.managers.booking_manager.Bot') as mock_bot_class:
            mock_bot = Mock()
            mock_bot.send_message = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            # Вызываем метод
            await BookingManager._notify_restaurant(
                booking_number, booking_data, restaurant_contact, user
            )
            
            # Проверяем что send_message был вызван
            assert mock_bot.send_message.called
            
            # Проверяем аргументы
            call_args = mock_bot.send_message.call_args
            chat_id = call_args[1]['chat_id']
            message = call_args[1]['text']
            
            # Символ = должен быть удален
            assert chat_id == 79219129292
            assert "#42" in message
            assert "John Doe" in message
            assert "19:30" in message
    
    @pytest.mark.asyncio
    async def test_notify_restaurant_with_username(self):
        """Тест отправки уведомления на username"""
        
        booking_number = 43
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(20, 0),
            'guests': 4
        }
        
        user = Mock()
        user.first_name = "Jane"
        user.last_name = ""
        user.username = "jane_user"
        user.id = 54321
        
        restaurant_contact = "=@test_restaurant"  # Username с символом =
        
        # Мокаем Bot
        with patch('src.bot.managers.booking_manager.Bot') as mock_bot_class:
            mock_bot = Mock()
            mock_bot.get_chat = AsyncMock()
            mock_bot.send_message = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            # Мокаем chat
            chat = Mock()
            chat.id = 98765
            mock_bot.get_chat.return_value = chat
            
            # Вызываем метод
            await BookingManager._notify_restaurant(
                booking_number, booking_data, restaurant_contact, user
            )
            
            # Проверяем что get_chat был вызван с правильным username
            mock_bot.get_chat.assert_called_with("test_restaurant")
            
            # Проверяем что send_message был вызван с chat.id
            assert mock_bot.send_message.called
            call_args = mock_bot.send_message.call_args
            assert call_args[1]['chat_id'] == 98765
    
    @pytest.mark.asyncio 
    async def test_notify_restaurant_with_group_chat_id(self):
        """Тест отправки уведомления в группу (отрицательный chat_id)"""
        
        booking_number = 44
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(18, 0),
            'guests': 3
        }
        
        user = Mock()
        user.first_name = "Bob"
        user.last_name = "Smith"
        user.username = "bobsmith"
        user.id = 67890
        
        restaurant_contact = "-1001234567890"  # Group chat ID
        
        # Мокаем Bot
        with patch('src.bot.managers.booking_manager.Bot') as mock_bot_class:
            mock_bot = Mock()
            mock_bot.send_message = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            # Вызываем метод
            await BookingManager._notify_restaurant(
                booking_number, booking_data, restaurant_contact, user
            )
            
            # Проверяем что send_message был вызван с отрицательным chat_id
            assert mock_bot.send_message.called
            call_args = mock_bot.send_message.call_args
            chat_id = call_args[1]['chat_id']
            assert chat_id == -1001234567890
    
    @pytest.mark.asyncio
    async def test_notify_restaurant_with_phone_formatted(self):
        """Тест обработки телефона с пробелами и дефисами"""
        
        booking_number = 45
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(21, 0),
            'guests': 1
        }
        
        user = Mock()
        user.first_name = "Alice"
        user.last_name = "Johnson"
        user.username = "alice_j"
        user.id = 11111
        
        restaurant_contact = "+7 921 912-92-92"  # Форматированный номер
        
        # Мокаем Bot
        with patch('src.bot.managers.booking_manager.Bot') as mock_bot_class:
            mock_bot = Mock()
            mock_bot.send_message = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            # Вызываем метод
            await BookingManager._notify_restaurant(
                booking_number, booking_data, restaurant_contact, user
            )
            
            # Проверяем что send_message был вызван с очищенными цифрами
            assert mock_bot.send_message.called
            call_args = mock_bot.send_message.call_args
            chat_id = call_args[1]['chat_id']
            assert chat_id == 79219129292  # Очищенные от пробелов и дефисов
    
    @pytest.mark.asyncio
    async def test_notify_restaurant_with_telegram_link(self):
        """Тест обработки ссылки t.me"""
        
        booking_number = 46
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(22, 0),
            'guests': 5
        }
        
        user = Mock()
        user.first_name = "Charlie"
        user.last_name = "Brown"
        user.username = "charlie_b"
        user.id = 22222
        
        restaurant_contact = "https://t.me/restaurant_owner"
        
        # Мокаем Bot
        with patch('src.bot.managers.booking_manager.Bot') as mock_bot_class:
            mock_bot = Mock()
            mock_bot.get_chat = AsyncMock()
            mock_bot.send_message = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            # Мокаем chat
            chat = Mock()
            chat.id = 33333
            mock_bot.get_chat.return_value = chat
            
            # Вызываем метод
            await BookingManager._notify_restaurant(
                booking_number, booking_data, restaurant_contact, user
            )
            
            # Проверяем что get_chat был вызван с извлеченным username
            mock_bot.get_chat.assert_called_with("restaurant_owner")
            
            # Проверяем отправку сообщения
            assert mock_bot.send_message.called
            call_args = mock_bot.send_message.call_args
            assert call_args[1]['chat_id'] == 33333
    
    @pytest.mark.asyncio
    async def test_notify_restaurant_error_handling(self):
        """Тест обработки ошибок при отправке уведомления"""
        
        booking_number = 47
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(17, 30),
            'guests': 2
        }
        
        user = Mock()
        user.first_name = "David"
        user.last_name = "Wilson"
        user.username = "david_w"
        user.id = 44444
        
        restaurant_contact = "@nonexistent_user"
        
        # Мокаем Bot с ошибкой
        with patch('src.bot.managers.booking_manager.Bot') as mock_bot_class:
            mock_bot = Mock()
            mock_bot.get_chat = AsyncMock(side_effect=Exception("User not found"))
            mock_bot_class.return_value = mock_bot
            
            # Мокаем logger
            with patch('src.bot.managers.booking_manager.logger') as mock_logger:
                
                # Вызываем метод - не должно падать с исключением
                await BookingManager._notify_restaurant(
                    booking_number, booking_data, restaurant_contact, user
                )
                
                # Проверяем что ошибка была залогирована
                assert mock_logger.warning.called
                assert mock_logger.info.called
    
    @pytest.mark.asyncio
    async def test_notify_restaurant_no_contact(self):
        """Тест обработки случая без контакта ресторана"""
        
        booking_number = 48
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(16, 0),
            'guests': 6
        }
        
        user = Mock()
        user.first_name = "Eva"
        user.last_name = "Garcia"
        user.username = "eva_g"
        user.id = 55555
        
        restaurant_contact = ""  # Пустой контакт
        
        # Мокаем logger
        with patch('src.bot.managers.booking_manager.logger') as mock_logger:
            
            # Вызываем метод
            await BookingManager._notify_restaurant(
                booking_number, booking_data, restaurant_contact, user
            )
            
            # Проверяем что была залогирована проблема с отсутствием контакта
            assert mock_logger.warning.called
            warning_call = mock_logger.warning.call_args[0][0]
            assert "No restaurant contact" in warning_call
    
    @pytest.mark.asyncio
    async def test_notify_restaurant_unknown_format(self):
        """Тест обработки неизвестного формата контакта"""
        
        booking_number = 49
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(15, 0),
            'guests': 3
        }
        
        user = Mock()
        user.first_name = "Frank"
        user.last_name = "Miller"
        user.username = "frank_m"
        user.id = 66666
        
        restaurant_contact = "unknown_format_contact"  # Неизвестный формат
        
        # Мокаем logger
        with patch('src.bot.managers.booking_manager.logger') as mock_logger:
            
            # Вызываем метод
            await BookingManager._notify_restaurant(
                booking_number, booking_data, restaurant_contact, user
            )
            
            # Проверяем что была залогирована проблема с неизвестным форматом
            assert mock_logger.warning.called
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Unknown contact format" in warning_call 