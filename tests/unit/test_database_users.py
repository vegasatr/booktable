"""
Unit тесты для модуля src.bot.database.users
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pytest
from unittest.mock import patch, MagicMock
from src.bot.database.users import (
    save_user_to_db, get_user_preferences, save_user_preferences
)

class TestSaveUserToDb:
    """Тесты для функции save_user_to_db"""
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_success(self, mock_get_db_connection):
        """Тест успешного сохранения пользователя"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        
        # Настраиваем fetchone для двух вызовов: CHECK (None) + INSERT (возврат client_number)
        mock_cur.fetchone.side_effect = [
            None,  # Первый вызов - проверка существования (пользователь не найден)
            {'client_number': 12345}  # Второй вызов - результат INSERT
        ]
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        result = save_user_to_db(
            user_id=123,
            username='testuser',
            first_name='Test',
            last_name='User',
            language='ru'
        )
        
        assert result is True
        assert mock_cur.execute.call_count == 2  # CHECK + INSERT
        mock_conn.commit.assert_called_once()
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_database_error(self, mock_get_db_connection):
        """Тест ошибки базы данных при сохранении пользователя"""
        mock_get_db_connection.side_effect = Exception("Database connection error")
        
        result = save_user_to_db(
            user_id=123,
            username='testuser',
            first_name='Test',
            last_name='User',
            language='ru'
        )
        
        assert result is False
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_with_none_values(self, mock_get_db_connection):
        """Тест сохранения пользователя с None значениями"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        
        # Настраиваем fetchone для CHECK (None) + INSERT
        mock_cur.fetchone.side_effect = [
            None,  # Проверка существования (пользователь не найден)
            {'client_number': 67890}  # Результат INSERT
        ]
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        result = save_user_to_db(
            user_id=123,
            username=None,
            first_name=None,
            last_name=None,
            language='en'
        )
        
        assert result is True
        assert mock_cur.execute.call_count == 2  # CHECK + INSERT
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_execute_error(self, mock_get_db_connection):
        """Тест ошибки выполнения SQL запроса"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = Exception("SQL Error")
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        result = save_user_to_db(
            user_id=123,
            username='testuser',
            first_name='Test',
            last_name='User',
            language='ru'
        )
        
        assert result is False

class TestGetUserPreferences:
    """Тесты для функции get_user_preferences"""
    
    @patch('src.bot.database.users.get_db_connection')
    def test_get_user_preferences_success(self, mock_get_db_connection):
        """Тест успешного получения предпочтений пользователя"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {
            'budget': '$$',
            'language': 'ru',
            'last_search_area': 'patong',
            'last_search_location': 'beach'
        }
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        result = get_user_preferences(123)
        
        assert result == {
            'budget': '$$', 
            'language': 'ru',
            'area': 'patong',
            'location': 'beach'
        }
        mock_cur.execute.assert_called_once()
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('src.bot.database.users.get_db_connection')
    def test_get_user_preferences_not_found(self, mock_get_db_connection):
        """Тест получения предпочтений несуществующего пользователя"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        result = get_user_preferences(999)
        
        assert result is None
    
    @patch('src.bot.database.users.get_db_connection')
    def test_get_user_preferences_database_error(self, mock_get_db_connection):
        """Тест ошибки базы данных при получении предпочтений"""
        mock_get_db_connection.side_effect = Exception("Database connection error")
        
        result = get_user_preferences(123)
        
        assert result is None
    
    @patch('src.bot.database.users.get_db_connection')
    def test_get_user_preferences_sql_error(self, mock_get_db_connection):
        """Тест ошибки SQL при получении предпочтений"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = Exception("SQL Error")
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        result = get_user_preferences(123)
        
        assert result is None

class TestSaveUserPreferences:
    """Тесты для функции save_user_preferences"""
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_preferences_success(self, mock_get_db_connection):
        """Тест успешного сохранения предпочтений пользователя"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        preferences = {'budget': '$$$', 'language': 'en'}
        result = save_user_preferences(123, preferences)
        
        assert result is True
        mock_cur.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_preferences_database_error(self, mock_get_db_connection):
        """Тест ошибки базы данных при сохранении предпочтений"""
        mock_get_db_connection.side_effect = Exception("Database connection error")
        
        preferences = {'budget': '$$$', 'language': 'en'}
        result = save_user_preferences(123, preferences)
        
        assert result is False
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_preferences_empty(self, mock_get_db_connection):
        """Тест сохранения пустых предпочтений"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        result = save_user_preferences(123, {})
        
        assert result is True
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_preferences_none(self, mock_get_db_connection):
        """Тест сохранения None предпочтений"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        result = save_user_preferences(123, None)
        
        assert result is False  # Должно возвращать False для None
    
    @patch('src.bot.database.users.get_db_connection')
    def test_save_user_preferences_sql_error(self, mock_get_db_connection):
        """Тест ошибки SQL при сохранении предпочтений"""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = Exception("SQL Error")
        mock_conn.cursor.return_value = mock_cur
        mock_get_db_connection.return_value = mock_conn
        
        preferences = {'budget': '$$$', 'language': 'en'}
        result = save_user_preferences(123, preferences)
        
        assert result is False 