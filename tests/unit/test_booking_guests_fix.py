"""
Тесты для исправленной обработки кастомного количества гостей
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date

@pytest.mark.asyncio
class TestBookingGuestsFix:
    """Тесты исправлений обработки количества гостей"""
    
    async def test_handle_custom_guests_simple_number(self):
        """Тест обработки простого числа"""
        from src.bot.handlers.booking_handlers import handle_custom_guests_input
        
        # Создаем мок объекты
        update = MagicMock()
        update.message.text = "55"
        update.message.reply_text = AsyncMock()
        
        context = MagicMock()
        context.user_data = {
            'booking_data': {
                'step': 'waiting_custom_guests'
            },
            'language': 'en'
        }
        
        with patch('src.bot.handlers.booking_handlers.BookingManager._ask_for_date', new_callable=AsyncMock) as mock_ask_date:
            result = await handle_custom_guests_input(update, context)
            
            assert result is True
            assert context.user_data['booking_data']['guests'] == 55
            assert context.user_data['booking_data']['step'] == 'date_selection'
            mock_ask_date.assert_called_once()
    
    async def test_handle_custom_guests_max_limit(self):
        """Тест превышения максимального лимита"""
        from src.bot.handlers.booking_handlers import handle_custom_guests_input
        
        # Создаем мок объекты
        update = MagicMock()
        update.message.text = "1500"
        update.message.reply_text = AsyncMock()
        update.message.chat_id = 123456
        
        context = MagicMock()
        context.user_data = {
            'booking_data': {
                'step': 'waiting_custom_guests'
            },
            'language': 'en'
        }
        context.bot.send_chat_action = AsyncMock()
        
        result = await handle_custom_guests_input(update, context)
        
        assert result is True
        update.message.reply_text.assert_called_with("Максимальное количество гостей: 999. Попробуйте еще раз.")
        assert 'guests' not in context.user_data['booking_data']
    
    async def test_handle_custom_guests_min_limit(self):
        """Тест минимального лимита"""
        from src.bot.handlers.booking_handlers import handle_custom_guests_input
        
        # Создаем мок объекты
        update = MagicMock()
        update.message.text = "0"
        update.message.reply_text = AsyncMock()
        update.message.chat_id = 123456
        
        context = MagicMock()
        context.user_data = {
            'booking_data': {
                'step': 'waiting_custom_guests'
            },
            'language': 'en'
        }
        context.bot.send_chat_action = AsyncMock()
        
        result = await handle_custom_guests_input(update, context)
        
        assert result is True
        update.message.reply_text.assert_called_with("Минимальное количество гостей: 1. Попробуйте еще раз.")
        assert 'guests' not in context.user_data['booking_data']
    
    async def test_handle_custom_guests_with_ai_fallback(self):
        """Тест обработки текста с помощью AI"""
        from src.bot.handlers.booking_handlers import handle_custom_guests_input
        
        # Создаем мок объекты
        update = MagicMock()
        update.message.text = "восемь человек"
        update.message.reply_text = AsyncMock()
        
        context = MagicMock()
        context.user_data = {
            'booking_data': {
                'step': 'waiting_custom_guests'
            },
            'language': 'en'
        }
        
        with patch('src.bot.handlers.booking_handlers.ai_generate', new_callable=AsyncMock) as mock_ai:
            with patch('src.bot.handlers.booking_handlers.BookingManager._ask_for_date', new_callable=AsyncMock) as mock_ask_date:
                mock_ai.return_value = "8"
                
                result = await handle_custom_guests_input(update, context)
                
                assert result is True
                assert context.user_data['booking_data']['guests'] == 8
                assert context.user_data['booking_data']['step'] == 'date_selection'
                mock_ask_date.assert_called_once()
                mock_ai.assert_called_once()
    
    async def test_ask_for_custom_guests_menu_button(self):
        """Тест что кнопка Меню присутствует при запросе кастомного количества гостей"""
        from src.bot.managers.booking_manager import BookingManager
        
        # Создаем мок объекты
        update = MagicMock()
        update.callback_query.edit_message_text = AsyncMock()
        update.effective_chat.id = 123456
        
        context = MagicMock()
        context.user_data = {
            'language': 'en',
            'booking_data': {}
        }
        context.bot.send_chat_action = AsyncMock()
        
        with patch('src.bot.managers.booking_manager.translate_message', new_callable=AsyncMock) as mock_translate:
            with patch('asyncio.sleep', new_callable=AsyncMock):
                mock_translate.return_value = "Пожалуйста, укажите количество гостей:"
                
                await BookingManager._ask_for_custom_guests(update, context)
                
                # Проверяем что вызвана функция с клавиатурой
                update.callback_query.edit_message_text.assert_called_once()
                call_args = update.callback_query.edit_message_text.call_args
                
                # Проверяем что передана клавиатура
                assert 'reply_markup' in call_args[1]
                keyboard = call_args[1]['reply_markup']
                
                # Проверяем что кнопка Меню есть
                assert len(keyboard.inline_keyboard) == 1
                assert len(keyboard.inline_keyboard[0]) == 1
                menu_button = keyboard.inline_keyboard[0][0]
                assert "МЕНЮ" in menu_button.text
                assert menu_button.callback_data == "main_menu" 