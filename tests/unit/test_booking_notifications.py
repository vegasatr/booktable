"""
Unit тесты для уведомлений при бронировании в боте менеджеров
"""
import pytest
import asyncio
from datetime import date, time as datetime_time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import psycopg2

class TestBookingNotifications:
    """Тесты уведомлений ресторанов при бронировании через бота менеджеров"""
    
    @pytest.mark.asyncio
    async def test_send_notification_success(self):
        """Тест успешной отправки уведомления через бота менеджеров"""
        
        # Подготовка данных
        booking_number = 123
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(19, 30),
            'guests': 2
        }
        restaurant_name = "Test Restaurant"
        user_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'username': 'johndoe',
            'id': 12345
        }
        
        # Мокаем соединение с базой данных
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Настраиваем данные ресторана
        mock_cursor.fetchone.return_value = {"booking_contact": "@test_manager"}
        
        # Импортируем и вызываем функцию с правильными патчами
        with patch('psycopg2.connect', return_value=mock_conn):
            # Импортируем после патча
            import bt_bookings_bot
            
            result = await bt_bookings_bot.send_booking_notification(
                booking_number, booking_data, restaurant_name, user_data
            )
        
        # Проверяем успешный результат
        assert result is True
        
        # Проверяем SQL запрос
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert "SELECT booking_contact" in query
        assert "FROM restaurants" in query
        assert "WHERE name = %s" in query
        assert params == (restaurant_name,)
    
    @pytest.mark.asyncio
    async def test_send_notification_no_restaurant_found(self):
        """Тест когда ресторан не найден"""
        
        booking_number = 999
        booking_data = {'date': date(2025, 5, 30), 'time': datetime_time(19, 30), 'guests': 2}
        restaurant_name = "Unknown Restaurant"
        user_data = {'first_name': 'John', 'username': 'johndoe'}
        
        # Мокаем соединение с базой данных
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Ресторан не найден
        mock_cursor.fetchone.return_value = None
        
        # Мокаем логгер
        with patch('psycopg2.connect', return_value=mock_conn):
            import bt_bookings_bot
            
            with patch.object(bt_bookings_bot, 'logger') as mock_logger:
                result = await bt_bookings_bot.send_booking_notification(
                    booking_number, booking_data, restaurant_name, user_data
                )
        
        # Проверяем результат
        assert result is False
        
        # Проверяем что была залогирована ошибка
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "No booking contact for restaurant" in warning_call
    
    @pytest.mark.asyncio
    async def test_send_notification_no_contact(self):
        """Тест когда у ресторана нет контакта"""
        
        booking_number = 124
        booking_data = {'date': date(2025, 5, 30), 'time': datetime_time(19, 30), 'guests': 2}
        restaurant_name = "Test Restaurant"
        user_data = {'first_name': 'John', 'username': 'johndoe'}
        
        # Мокаем соединение с базой данных
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Ресторан без контакта
        mock_cursor.fetchone.return_value = {"booking_contact": None}
        
        # Мокаем логгер
        with patch('psycopg2.connect', return_value=mock_conn):
            import bt_bookings_bot
            
            with patch.object(bt_bookings_bot, 'logger') as mock_logger:
                result = await bt_bookings_bot.send_booking_notification(
                    booking_number, booking_data, restaurant_name, user_data
                )
        
        # Проверяем результат
        assert result is False
        
        # Проверяем что была залогирована ошибка
        mock_logger.warning.assert_called_once()
        warning_call = mock_logger.warning.call_args[0][0]
        assert "No booking contact for restaurant" in warning_call
    
    @pytest.mark.asyncio
    async def test_send_notification_with_username_only(self):
        """Тест когда у пользователя только username"""
        
        booking_number = 125
        booking_data = {'date': date(2025, 5, 30), 'time': datetime_time(19, 30), 'guests': 2}
        restaurant_name = "Test Restaurant"
        user_data = {'username': 'johndoe', 'id': 12345}  # Только username и id
        
        # Мокаем соединение с базой данных
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Ресторан с контактом
        mock_cursor.fetchone.return_value = {"booking_contact": "@manager"}
        
        with patch('psycopg2.connect', return_value=mock_conn):
            import bt_bookings_bot
            
            result = await bt_bookings_bot.send_booking_notification(
                booking_number, booking_data, restaurant_name, user_data
            )
        
        # Проверяем успешный результат
        assert result is True
    
    @pytest.mark.asyncio
    async def test_send_notification_with_id_only(self):
        """Тест когда у пользователя только id"""
        
        booking_number = 126
        booking_data = {'date': date(2025, 5, 30), 'time': datetime_time(19, 30), 'guests': 2}
        restaurant_name = "Test Restaurant"
        user_data = {'id': 12345}  # Только id
        
        # Мокаем соединение с базой данных
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Ресторан с контактом
        mock_cursor.fetchone.return_value = {"booking_contact": "@manager"}
        
        with patch('psycopg2.connect', return_value=mock_conn):
            import bt_bookings_bot
            
            result = await bt_bookings_bot.send_booking_notification(
                booking_number, booking_data, restaurant_name, user_data
            )
        
        # Проверяем успешный результат
        assert result is True
    
    @pytest.mark.asyncio
    async def test_send_notification_database_error(self):
        """Тест обработки ошибки базы данных"""
        
        booking_number = 127
        booking_data = {'date': date(2025, 5, 30), 'time': datetime_time(19, 30), 'guests': 2}
        restaurant_name = "Test Restaurant"
        user_data = {'first_name': 'John', 'username': 'johndoe'}
        
        # Мокаем ошибку базы данных
        with patch('psycopg2.connect', side_effect=psycopg2.Error("DB connection failed")):
            import bt_bookings_bot
            
            with patch.object(bt_bookings_bot, 'logger') as mock_logger:
                result = await bt_bookings_bot.send_booking_notification(
                    booking_number, booking_data, restaurant_name, user_data
                )
        
        # Проверяем результат
        assert result is False
        
        # Проверяем что была залогирована ошибка
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error sending booking notification" in error_call
    
    @pytest.mark.asyncio
    async def test_send_notification_message_formatting(self):
        """Тест правильного форматирования сообщения уведомления"""
        
        booking_number = 128
        booking_data = {
            'date': date(2025, 5, 30),
            'time': datetime_time(19, 30),
            'guests': 4
        }
        restaurant_name = "Test Restaurant"
        user_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'username': 'johndoe',
            'id': 12345
        }
        
        # Мокаем соединение с базой данных
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Ресторан с контактом
        mock_cursor.fetchone.return_value = {"booking_contact": "@manager"}
        
        with patch('psycopg2.connect', return_value=mock_conn):
            import bt_bookings_bot
            
            # Мокаем логгер чтобы увидеть сформированное сообщение
            with patch.object(bt_bookings_bot, 'logger') as mock_logger:
                result = await bt_bookings_bot.send_booking_notification(
                    booking_number, booking_data, restaurant_name, user_data
                )
        
        # Проверяем успешный результат
        assert result is True
        
        # Проверяем что сообщение содержит нужные данные
        info_calls = [call for call in mock_logger.info.call_args_list]
        message_logged = False
        for call in info_calls:
            if "Booking notification prepared" in call[0][0]:
                message_logged = True
                message = call[0][0]
                assert "Booking number: 128" in message
                assert "Test Restaurant" in message
                break
        
        assert message_logged, "Booking notification message should be logged" 