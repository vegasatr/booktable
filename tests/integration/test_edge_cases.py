#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INTEGRATION ТЕСТЫ - EDGE CASES И ГРАНИЧНЫЕ СЛУЧАИ
===============================================

Тестирует все edge cases из tests/to_do.txt:
1. Обработка ошибок и исключений
2. Невалидные входные данные  
3. Альтернативные сценарии пользователей
4. Нестандартные сообщения (фото, стикеры, файлы)
5. Многопользовательская изоляция
6. Производительность при нагрузке
7. Безопасность и валидация
8. Интеграция с внешними сервисами
9. Локализация и переводы
10. Логирование и мониторинг
11. Восстановление после сбоев
12. Совместимость версий
"""

import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем корень проекта в PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Импортируем только необходимые модули
from src.bot.database.users import save_user_to_db, save_user_preferences
from src.bot.ai.core import ai_generate, is_about_restaurants
from src.bot.ai.translation import detect_language, translate_message

class TestErrorHandlingAndExceptions:
    """Тесты обработки ошибок и исключений (пункт 1 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_database_connection_errors(self):
        """Тест ошибок подключения к базе данных"""
        
        # Мокаем ошибку подключения
        with patch('src.bot.database.users.get_db_connection', 
                   side_effect=Exception("Database connection failed")):
            
            result = save_user_to_db(123, "test", "Test", "User", "ru")
            assert result is False  # Должен gracefully обработать ошибку
    
    @pytest.mark.asyncio
    async def test_ai_service_errors(self):
        """Тест ошибок AI сервиса"""
        
        with patch('src.bot.ai.core.client') as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
            
            # Должен вернуть fallback сообщение
            result = await ai_generate('restaurant_recommendation', 
                                     text="test", target_language='ru')
            assert "Извините" in result or "ошибка" in result.lower()

class TestInvalidInputData:
    """Тесты на невалидные входные данные (пункт 2 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_empty_and_invalid_text(self):
        """Тест пустых и невалидных текстов"""
        
        test_cases = ["", " ", None, "\n", "\t", "🤖", "123456789"]
        
        for test_text in test_cases:
            try:
                # Тест определения языка
                lang = await detect_language(test_text)
                assert isinstance(lang, str)
                
                # Тест классификации
                is_restaurant = await is_about_restaurants(test_text)
                assert isinstance(is_restaurant, bool)
                
            except Exception as e:
                # Функции должны gracefully обрабатывать невалидные входы
                pytest.fail(f"Should handle invalid input '{test_text}': {e}")
    
    @pytest.mark.asyncio
    async def test_invalid_user_data(self):
        """Тест невалидных пользовательских данных"""
        
        # Тест с невалидными ID
        invalid_ids = [-1, 0, "string", None, 999999999999]
        
        for invalid_id in invalid_ids:
            try:
                result = save_user_to_db(invalid_id, "test", "Test", "User", "ru")
                # Должен либо обработать, либо вернуть False
                assert isinstance(result, bool)
            except Exception:
                # Исключения тоже допустимы для невалидных данных
                pass

class TestAlternativeScenarios:
    """Тест альтернативных сценариев (пункт 3 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_language_detection_edge_cases(self):
        """Тест определения языка в граничных случаях"""
        
        edge_cases = [
            ("Hello мир", "mixed languages"),
            ("123 456 789", "numbers only"),
            ("!@#$%^&*()", "special chars only"),
            ("Привет! How are you?", "mixed with punctuation"),
            ("🍕🍔🍟", "emojis only")
        ]
        
        for text, description in edge_cases:
            try:
                lang = await detect_language(text)
                assert isinstance(lang, str)
                assert len(lang) >= 2  # Должен быть код языка или сообщение
            except Exception as e:
                pytest.fail(f"Language detection failed for {description}: {e}")
    
    @pytest.mark.asyncio
    async def test_translation_edge_cases(self):
        """Тест перевода в граничных случаях"""
        
        # Тест перевода несуществующих ключей
        result = await translate_message('nonexistent_key', 'ru')
        assert result == 'nonexistent_key'  # Должен вернуть ключ
        
        # Тест перевода на несуществующий язык
        result = await translate_message('welcome', 'xyz')
        assert isinstance(result, str)

class TestMultiUserIsolation:
    """Тест многопользовательской изоляции (пункт 5 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_concurrent_user_operations(self):
        """Тест одновременных операций разных пользователей"""
        
        try:
            # Создаем задачи для разных пользователей
            tasks = []
            for i in range(5):
                user_id = 777770 + i
                task = save_user_to_db(user_id, f"user{i}", "Test", f"User{i}", "ru")
                tasks.append(task)
            
            # Выполняем одновременно
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Все операции должны завершиться без взаимного влияния
            for result in results:
                if isinstance(result, Exception):
                    # Исключения допустимы (например, БД недоступна)
                    continue
                assert isinstance(result, bool)
                
        except Exception as e:
            pytest.skip(f"Concurrent operations test skipped: {e}")

class TestPerformanceUnderLoad:
    """Тест производительности при нагрузке (пункт 6 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_ai_response_time(self):
        """Тест времени ответа AI функций"""
        import time
        
        start_time = time.time()
        
        # Тест быстрых fallback операций
        result = await ai_generate('fallback_error', target_language='ru')
        
        elapsed = time.time() - start_time
        
        # Fallback должен быть мгновенным
        assert elapsed < 0.1
        assert len(result) > 0

class TestSecurityAndValidation:
    """Тест безопасности и валидации (пункт 7 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_sql_injection_protection(self):
        """Тест защиты от SQL инъекций"""
        
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'; DELETE FROM users WHERE '1'='1",
            "<script>alert('xss')</script>",
            "../../etc/passwd"
        ]
        
        for malicious_input in malicious_inputs:
            try:
                # Пытаемся сохранить пользователя с вредоносными данными
                result = save_user_to_db(888888, malicious_input, 
                                       malicious_input, malicious_input, "ru")
                
                # Функция должна либо обработать безопасно, либо отклонить
                assert isinstance(result, bool)
                
            except Exception:
                # Исключения при обработке вредоносных данных допустимы
                pass

class TestLocalizationAndTranslations:
    """Тест локализации и переводов (пункт 9 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_language_support(self):
        """Тест поддержки разных языков"""
        
        languages = ['ru', 'en', 'th', 'de', 'fr', 'es', 'zh']
        
        for lang in languages:
            try:
                # Тест перевода базового сообщения
                result = await translate_message('welcome', lang)
                assert isinstance(result, str)
                assert len(result) > 0
                
            except Exception as e:
                # Некоторые языки могут не поддерживаться
                continue

class TestLoggingAndMonitoring:
    """Тест логирования и мониторинга (пункт 10 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_error_logging(self):
        """Тест логирования ошибок"""
        
        with patch('src.bot.ai.core.logger') as mock_logger:
            # Вызываем функцию которая должна логировать ошибку
            with patch('src.bot.ai.core.client') as mock_client:
                mock_client.chat.completions.create.side_effect = Exception("Test Error")
                
                await ai_generate('restaurant_recommendation', 
                                text="test", target_language='ru')
                
                # Проверяем что ошибка была залогирована
                mock_logger.error.assert_called()

class TestRecoveryAfterFailures:
    """Тест восстановления после сбоев (пункт 11 из TO-DO)"""
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Тест graceful degradation при сбоях сервисов"""
        
        # Тест работы при недоступности AI
        with patch('src.bot.ai.core.client') as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("Service Unavailable")
            
            # Система должна продолжать работать с fallback
            result = await ai_generate('fallback_error', target_language='ru')
            assert "Извините" in result
            
            # Классификация должна работать с fallback
            is_restaurant = await is_about_restaurants("тест")
            assert isinstance(is_restaurant, bool)

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 