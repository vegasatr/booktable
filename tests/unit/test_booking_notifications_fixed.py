"""
Unit тесты для исправленной системы уведомлений при бронировании
"""
import pytest
import asyncio
from datetime import date, time as datetime_time
from unittest.mock import Mock, patch, AsyncMock, MagicMock

class TestFixedBookingNotifications:
    """Тесты исправленной системы уведомлений"""
    
    @pytest.mark.asyncio
    async def test_send_to_managers_bot_username_format(self):
        """Тест отправки через бот менеджеров с @username"""
        
        # Мокаем класс Bot
        mock_bot = AsyncMock()
        mock_chat = Mock()
        mock_chat.id = 12345
        mock_bot.get_chat.return_value = mock_chat
        mock_bot.send_message = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.Bot', return_value=mock_bot):
            from src.bot.managers.booking_manager import BookingManager
            
            result = await BookingManager._send_to_managers_bot(
                booking_number=123,
                restaurant_name="Test Restaurant",
                message="Test message",
                contact="@testuser"
            )
        
        # Проверяем успешный результат
        assert result is True
        mock_bot.get_chat.assert_called_once_with("testuser")
        mock_bot.send_message.assert_called_once_with(chat_id=12345, text="Test message")
    
    @pytest.mark.asyncio
    async def test_send_to_managers_bot_equals_username_format(self):
        """Тест отправки с форматом =@username"""
        
        mock_bot = AsyncMock()
        mock_chat = Mock()
        mock_chat.id = 12345
        mock_bot.get_chat.return_value = mock_chat
        mock_bot.send_message = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.Bot', return_value=mock_bot):
            from src.bot.managers.booking_manager import BookingManager
            
            result = await BookingManager._send_to_managers_bot(
                booking_number=124,
                restaurant_name="Test Restaurant",
                message="Test message",
                contact="=@testuser"
            )
        
        assert result is True
        mock_bot.get_chat.assert_called_once_with("testuser")
        mock_bot.send_message.assert_called_once_with(chat_id=12345, text="Test message")
    
    @pytest.mark.asyncio
    async def test_send_to_managers_bot_chat_id_format(self):
        """Тест отправки с числовым chat_id"""
        
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.Bot', return_value=mock_bot):
            from src.bot.managers.booking_manager import BookingManager
            
            result = await BookingManager._send_to_managers_bot(
                booking_number=125,
                restaurant_name="Test Restaurant",
                message="Test message",
                contact="5419235215"
            )
        
        assert result is True
        mock_bot.send_message.assert_called_once_with(chat_id=5419235215, text="Test message")
    
    @pytest.mark.asyncio
    async def test_send_to_managers_bot_no_contact(self):
        """Тест когда контакт не предоставлен"""
        
        with patch('src.bot.managers.booking_manager.Bot'):
            from src.bot.managers.booking_manager import BookingManager
            
            result = await BookingManager._send_to_managers_bot(
                booking_number=126,
                restaurant_name="Test Restaurant", 
                message="Test message",
                contact=""
            )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_managers_bot_unknown_format(self):
        """Тест с неизвестным форматом контакта"""
        
        with patch('src.bot.managers.booking_manager.Bot'):
            from src.bot.managers.booking_manager import BookingManager
            
            result = await BookingManager._send_to_managers_bot(
                booking_number=127,
                restaurant_name="Test Restaurant",
                message="Test message", 
                contact="unknown_format"
            )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_notify_restaurant_fallback_system(self):
        """Тест fallback системы при ошибке бота менеджеров"""
        
        mock_user = Mock()
        mock_user.id = 12345
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        
        booking_data = {
            'date': date(2025, 5, 31),
            'time': datetime_time(19, 30),
            'guests': 2,
            'restaurant': {'name': 'Test Restaurant'}
        }
        
        # Мокаем неудачную отправку через бот менеджеров
        with patch('src.bot.managers.booking_manager.BookingManager._send_to_managers_bot', return_value=False) as mock_managers_bot:
            with patch('src.bot.managers.booking_manager.BookingManager._send_direct_notification') as mock_direct:
                from src.bot.managers.booking_manager import BookingManager
                
                await BookingManager._notify_restaurant(
                    booking_number=128,
                    booking_data=booking_data,
                    restaurant_contact="@testuser",
                    user=mock_user
                )
        
        # Проверяем что была попытка через бот менеджеров и fallback
        mock_managers_bot.assert_called_once()
        mock_direct.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_notification_flow(self):
        """Интеграционный тест полного потока уведомления"""
        
        mock_user = Mock()
        mock_user.id = 12345
        mock_user.username = "testuser"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        
        booking_data = {
            'date': date(2025, 5, 31),
            'time': datetime_time(19, 30),
            'guests': 2,
            'restaurant': {'name': 'Test Restaurant'}
        }
        
        # Мокаем успешную отправку
        mock_bot = AsyncMock()
        mock_chat = Mock()
        mock_chat.id = 54321
        mock_bot.get_chat.return_value = mock_chat
        mock_bot.send_message = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.Bot', return_value=mock_bot):
            from src.bot.managers.booking_manager import BookingManager
            
            await BookingManager._notify_restaurant(
                booking_number=129,
                booking_data=booking_data,
                restaurant_contact="@testuser",
                user=mock_user
            )
        
        # Проверяем что сообщение было отправлено
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args[1]['chat_id'] == 54321
        assert "НОВОЕ БРОНИРОВАНИЕ" in call_args[1]['text']
        assert "#129" in call_args[1]['text']
        assert "Test User" in call_args[1]['text'] 