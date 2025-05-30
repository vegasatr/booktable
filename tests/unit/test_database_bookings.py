"""
Unit тесты для модуля database/bookings.py
"""
import pytest
import asyncio
from datetime import date, time, datetime
from unittest.mock import Mock, patch, AsyncMock

from src.bot.database.bookings import (
    save_booking_to_db, get_booking_by_number, 
    update_booking_preferences, get_restaurant_working_hours
)

class TestBookingDatabase:
    """Тесты для работы с базой данных бронирований"""
    
    @pytest.mark.asyncio
    async def test_save_booking_to_db_success(self):
        """Тест успешного сохранения бронирования"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = {'booking_number': 123}
            
            # Тестовые данные
            restaurant_name = "Test Restaurant"
            client_name = "John Doe"
            phone = "+1234567890"
            date_booking = date(2024, 6, 15)
            time_booking = time(19, 30)
            guests = 2
            restaurant_contact = "test_contact"
            
            result = await save_booking_to_db(
                restaurant_name=restaurant_name,
                client_name=client_name,
                phone=phone,
                date_booking=date_booking,
                time_booking=time_booking,
                guests=guests,
                restaurant_contact=restaurant_contact,
                client_code=12345
            )
            
            # Проверяем результат
            assert result == 123
            
            # Проверяем что был выполнен правильный запрос
            mock_cur.execute.assert_called_once()
            call_args = mock_cur.execute.call_args
            
            # Проверяем структуру запроса
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert "INSERT INTO bookings" in query
            assert "RETURNING booking_number" in query
            
            # Проверяем параметры
            assert params[0] == date_booking  # date
            assert params[1] == time_booking  # time
            assert params[2] == client_name
            assert params[3] == phone
            assert params[4] == guests
            assert params[5] == restaurant_name
            assert params[6] == "telegram"  # booking_method
            assert params[7] == restaurant_contact
            assert params[9] == "12345"  # client_code as string
            assert params[10] == "pending"  # status
            
            # Проверяем что транзакция была зафиксирована
            mock_conn.commit.assert_called_once()
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_booking_to_db_error(self):
        """Тест обработки ошибки при сохранении бронирования"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            
            # Симулируем ошибку базы данных
            mock_cur.execute.side_effect = Exception("Database error")
            
            result = await save_booking_to_db(
                restaurant_name="Test",
                client_name="Test User",
                phone="123",
                date_booking=date.today(),
                time_booking=time(19, 0),
                guests=2,
                restaurant_contact="test"
            )
            
            # Проверяем что вернулся None при ошибке
            assert result is None
            
            # Проверяем что был сделан rollback
            mock_conn.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_booking_by_number_success(self):
        """Тест успешного получения бронирования по номеру"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            
            # Мокаем результат запроса
            mock_booking_data = {
                'booking_number': 123,
                'restaurant': 'Test Restaurant',
                'client_name': 'John Doe',
                'date': date(2024, 6, 15),
                'time': time(19, 30),
                'guests': 2,
                'status': 'pending'
            }
            mock_cur.fetchone.return_value = mock_booking_data
            
            result = await get_booking_by_number(123)
            
            # Проверяем результат
            assert result == mock_booking_data
            
            # Проверяем что был выполнен правильный запрос
            mock_cur.execute.assert_called_once_with(
                "SELECT * FROM bookings WHERE booking_number = %s",
                (123,)
            )
    
    @pytest.mark.asyncio
    async def test_get_booking_by_number_not_found(self):
        """Тест получения несуществующего бронирования"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = None
            
            result = await get_booking_by_number(999)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_update_booking_preferences_success(self):
        """Тест успешного обновления пожеланий"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            
            # Мокаем существующие пожелания
            mock_cur.fetchone.return_value = {'preferences': 'Window table'}
            
            result = await update_booking_preferences(123, 'With sea view')
            
            assert result is True
            
            # Проверяем что были выполнены правильные запросы
            assert mock_cur.execute.call_count == 2
            
            # Первый запрос - получение текущих пожеланий
            first_call = mock_cur.execute.call_args_list[0]
            assert "SELECT preferences FROM bookings" in first_call[0][0]
            assert first_call[0][1] == (123,)
            
            # Второй запрос - обновление пожеланий
            second_call = mock_cur.execute.call_args_list[1]
            assert "UPDATE bookings SET preferences" in second_call[0][0]
            
            # Проверяем что пожелания объединились
            updated_preferences = second_call[0][1][0]
            assert "Window table" in updated_preferences
            assert "With sea view" in updated_preferences
            
            mock_conn.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_booking_preferences_not_found(self):
        """Тест обновления пожеланий для несуществующего бронирования"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = None
            
            result = await update_booking_preferences(999, 'Some preferences')
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_restaurant_working_hours_success(self):
        """Тест успешного получения времени работы ресторана"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            
            # Мокаем данные ресторана
            mock_restaurant_data = {
                'working_hours': {'open': '18:00', 'close': '23:00'},
                'booking_method': 'telegram',
                'booking_contact': '@restaurant_contact'
            }
            mock_cur.fetchone.return_value = mock_restaurant_data
            
            result = await get_restaurant_working_hours('Test Restaurant')
            
            assert result == mock_restaurant_data
            
            # Проверяем что был выполнен правильный запрос
            mock_cur.execute.assert_called_once()
            call_args = mock_cur.execute.call_args
            
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert "SELECT working_hours, booking_method, booking_contact" in query
            assert "FROM restaurants" in query
            assert "WHERE name = %s AND active = true" in query
            assert params == ('Test Restaurant',)
    
    @pytest.mark.asyncio
    async def test_get_restaurant_working_hours_not_found(self):
        """Тест получения данных несуществующего ресторана"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = None
            
            result = await get_restaurant_working_hours('Nonexistent Restaurant')
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_save_booking_with_all_optional_params(self):
        """Тест сохранения бронирования со всеми опциональными параметрами"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = {'booking_number': 456}
            
            result = await save_booking_to_db(
                restaurant_name="Fancy Restaurant",
                client_name="Jane Smith",
                phone="+9876543210",
                date_booking=date(2024, 12, 25),
                time_booking=time(20, 0),
                guests=4,
                restaurant_contact="@fancy_restaurant",
                booking_method="whatsapp",
                preferences="Vegetarian menu",
                client_code=54321,
                status="confirmed"
            )
            
            assert result == 456
            
            # Проверяем что все параметры переданы правильно
            call_args = mock_cur.execute.call_args[0][1]
            assert call_args[6] == "whatsapp"  # booking_method
            assert call_args[8] == "Vegetarian menu"  # preferences
            assert call_args[9] == "54321"  # client_code
            assert call_args[10] == "confirmed"  # status

class TestBookingDatabaseEdgeCases:
    """Тесты для edge cases в работе с базой данных"""
    
    @pytest.mark.asyncio
    async def test_save_booking_with_empty_preferences(self):
        """Тест сохранения бронирования с пустыми пожеланиями"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = {'booking_number': 789}
            
            result = await save_booking_to_db(
                restaurant_name="Test",
                client_name="Test User",
                phone="",
                date_booking=date.today(),
                time_booking=time(19, 0),
                guests=1,
                restaurant_contact="",
                preferences=""
            )
            
            assert result == 789
            
            # Проверяем что пустые значения обработаны корректно
            call_args = mock_cur.execute.call_args[0][1]
            assert call_args[3] == ""  # phone
            assert call_args[7] == ""  # restaurant_contact
            assert call_args[8] == ""  # preferences
    
    @pytest.mark.asyncio
    async def test_update_preferences_with_empty_current(self):
        """Тест обновления пожеланий когда текущие пожелания пустые"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = {'preferences': None}
            
            result = await update_booking_preferences(123, 'New preference')
            
            assert result is True
            
            # Проверяем что новые пожелания записались без проблем
            second_call = mock_cur.execute.call_args_list[1]
            updated_preferences = second_call[0][1][0]
            assert updated_preferences == 'New preference'
    
    @pytest.mark.asyncio
    async def test_database_connection_error(self):
        """Тест обработки ошибки подключения к базе данных"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_get_conn.side_effect = Exception("Connection failed")
            
            result = await save_booking_to_db(
                restaurant_name="Test",
                client_name="Test",
                phone="123",
                date_booking=date.today(),
                time_booking=time(19, 0),
                guests=2,
                restaurant_contact=""
            )
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_unicode_handling(self):
        """Тест обработки unicode символов в данных бронирования"""
        with patch('src.bot.database.bookings.get_db_connection') as mock_get_conn:
            mock_conn = Mock()
            mock_cur = Mock()
            
            mock_get_conn.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = {'booking_number': 999}
            
            # Данные с unicode символами
            result = await save_booking_to_db(
                restaurant_name="Ресторан Тест",
                client_name="Иван Петров",
                phone="+7-999-123-45-67",
                date_booking=date.today(),
                time_booking=time(19, 30),
                guests=2,
                restaurant_contact="@ресторан_контакт",
                preferences="Столик у окна, без острого"
            )
            
            assert result == 999
            
            # Проверяем что unicode данные переданы корректно
            call_args = mock_cur.execute.call_args[0][1]
            assert call_args[5] == "Ресторан Тест"
            assert call_args[2] == "Иван Петров"
            assert call_args[8] == "Столик у окна, без острого" 