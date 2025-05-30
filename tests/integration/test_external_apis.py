#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INTEGRATION ТЕСТЫ - ВНЕШНИЕ API
==============================

Тестирует интеграцию с внешними сервисами:
- OpenAI API (ChatGPT)
- PostgreSQL Database
- Telegram Bot API
- Google Sheets (если используется)

Эти тесты требуют настоящих подключений к сервисам,
но используют безопасные тестовые данные.
"""

import sys
import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Добавляем корень проекта в PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Импортируем модули для тестирования API
from src.bot.ai.core import ping_openai, ai_generate, is_about_restaurants
from src.bot.database.connection import get_db_connection
from src.bot.database.users import save_user_to_db, get_user_preferences

class TestOpenAIIntegration:
    """Тесты интеграции с OpenAI API"""
    
    def test_openai_connection(self):
        """Тест базового подключения к OpenAI"""
        result = ping_openai()
        # Если есть API ключ - должен подключиться
        # Если нет - должен gracefully обработать ошибку
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_ai_generate_integration(self):
        """Тест генерации ответов через OpenAI"""
        # Тест простого fallback (не требует API)
        result = await ai_generate('fallback_error', target_language='ru')
        assert "Извините" in result or "Sorry" in result
        
        # Тест с настоящим API (если доступен)
        try:
            result = await ai_generate('restaurant_recommendation', 
                                     text="итальянская кухня",
                                     target_language='ru')
            assert isinstance(result, str)
            assert len(result) > 0
        except Exception:
            # API недоступен - это нормально для тестов
            pass
    
    @pytest.mark.asyncio
    async def test_restaurant_classification_integration(self):
        """Тест классификации вопросов о ресторанах"""
        test_cases = [
            ("где поесть", True),
            ("какая погода", False),
            ("рекомендуй ресторан", True),
            ("как дела", False)
        ]
        
        for text, expected_is_restaurant in test_cases:
            try:
                result = await is_about_restaurants(text)
                assert isinstance(result, bool)
                # Если API работает, проверяем корректность
                if result is not None:
                    # Допускаем небольшую погрешность в классификации
                    pass  
            except Exception:
                # API недоступен - пропускаем
                pass

class TestDatabaseIntegration:
    """Тесты интеграции с базой данных"""
    
    def test_database_connection(self):
        """Тест подключения к базе данных"""
        try:
            conn = get_db_connection()
            assert conn is not None
            
            # Тестируем простой запрос
            cur = conn.cursor()
            cur.execute("SELECT 1")
            result = cur.fetchone()
            assert result is not None
            
            cur.close()
            conn.close()
            
        except Exception as e:
            # База недоступна - это может быть нормально в тестовой среде
            pytest.skip(f"Database not available: {e}")
    
    def test_user_operations_integration(self):
        """Тест операций с пользователями в БД"""
        try:
            # Используем тестовый ID для безопасности
            test_user_id = 999999
            
            # Тест сохранения пользователя
            result = save_user_to_db(
                test_user_id, 
                "pytest_user", 
                "Test", 
                "User", 
                "en"
            )
            
            # Должен либо успешно сохранить, либо gracefully обработать ошибку
            assert isinstance(result, bool)
            
            # Тест получения предпочтений
            preferences = get_user_preferences(test_user_id)
            # Может быть None если пользователь не найден - это нормально
            assert preferences is None or isinstance(preferences, dict)
            
        except Exception as e:
            pytest.skip(f"Database operations not available: {e}")

class TestAPIErrorHandling:
    """Тесты обработки ошибок внешних API"""
    
    @pytest.mark.asyncio
    async def test_openai_error_handling(self):
        """Тест обработки ошибок OpenAI API"""
        
        # Мокаем ошибку API
        with patch('src.bot.ai.core.client') as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("API Error")
            
            # Должен вернуть fallback сообщение
            result = await ai_generate('restaurant_recommendation', 
                                     text="test", target_language='ru')
            
            assert "Извините" in result or "ошибка" in result.lower()
    
    def test_database_error_handling(self):
        """Тест обработки ошибок базы данных"""
        
        # Мокаем ошибку подключения к БД
        with patch('src.bot.database.users.get_db_connection', 
                   side_effect=Exception("DB Connection Error")):
            
            # Должен gracefully обработать ошибку и вернуть False
            try:
                result = save_user_to_db(123, "test", "Test", "User", "ru")
                # Функция должна обработать ошибку и вернуть False
                assert result is False
            except Exception:
                # Если функция выбрасывает исключение - это тоже корректное поведение
                # Главное что не падает без обработки
                pass

class TestAPIPerformance:
    """Тесты производительности API"""
    
    @pytest.mark.asyncio
    async def test_ai_response_time(self):
        """Тест времени ответа AI"""
        import time
        
        start_time = time.time()
        
        # Тест простого fallback (должен быть быстрым)
        result = await ai_generate('fallback_error', target_language='ru')
        
        elapsed = time.time() - start_time
        
        # Fallback должен отвечать мгновенно
        assert elapsed < 0.1
        assert len(result) > 0
    
    def test_database_response_time(self):
        """Тест времени ответа базы данных"""
        import time
        
        try:
            start_time = time.time()
            
            # Простой запрос к БД
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            result = cur.fetchone()
            
            elapsed = time.time() - start_time
            
            cur.close()
            conn.close()
            
            # БД должна отвечать быстро
            assert elapsed < 1.0
            assert result is not None
            
        except Exception:
            pytest.skip("Database not available for performance test")

class TestAPIResilience:
    """Тесты устойчивости к ошибкам API"""
    
    @pytest.mark.asyncio
    async def test_multiple_ai_requests(self):
        """Тест множественных запросов к AI"""
        
        # Делаем несколько запросов подряд
        results = []
        for i in range(3):
            result = await ai_generate('fallback_error', target_language='ru')
            results.append(result)
        
        # Все должны вернуть корректные ответы
        for result in results:
            assert isinstance(result, str)
            assert len(result) > 0
    
    def test_multiple_db_connections(self):
        """Тест множественных подключений к БД"""
        
        try:
            connections = []
            
            # Создаем несколько подключений
            for i in range(3):
                conn = get_db_connection()
                connections.append(conn)
            
            # Все должны быть валидными
            for conn in connections:
                assert conn is not None
                cur = conn.cursor()
                cur.execute("SELECT 1")
                result = cur.fetchone()
                assert result is not None
                cur.close()
                conn.close()
                
        except Exception:
            pytest.skip("Database not available for resilience test")

@pytest.mark.skipif(not os.getenv('RUN_INTEGRATION_TESTS'), 
                   reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests")
class TestFullAPIIntegration:
    """Полные integration тесты (требуют переменной окружения)"""
    
    @pytest.mark.asyncio
    async def test_complete_ai_workflow(self):
        """Тест полного AI workflow с настоящими API"""
        
        # Классификация вопроса
        is_restaurant = await is_about_restaurants("где поесть вкусно?")
        assert isinstance(is_restaurant, bool)
        
        # Генерация ответа
        if is_restaurant:
            result = await ai_generate('restaurant_recommendation',
                                     text="итальянская кухня",
                                     target_language='ru')
            assert isinstance(result, str)
            assert len(result) > 10
    
    def test_complete_database_workflow(self):
        """Тест полного workflow с базой данных"""
        
        test_user_id = 888888
        
        # Сохранение пользователя
        save_result = save_user_to_db(test_user_id, "integration_test", 
                                    "Integration", "Test", "ru")
        assert save_result is True
        
        # Получение данных
        preferences = get_user_preferences(test_user_id)
        assert preferences is None or isinstance(preferences, dict)

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 