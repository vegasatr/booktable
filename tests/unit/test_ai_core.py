"""
Unit тесты для модуля src.bot.ai.core
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.bot.ai.core import (
    ping_openai, ai_generate, ask, restaurant_chat, 
    detect_area_from_text, general_chat, is_about_restaurants,
    get_relevant_restaurant_data
)

class TestPingOpenAI:
    """Тесты для функции ping_openai"""
    
    @patch('src.bot.ai.core.client')
    def test_ping_openai_success(self, mock_client):
        """Тест успешного ping OpenAI"""
        mock_client.chat.completions.create.return_value = True
        result = ping_openai()
        assert result is True
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('src.bot.ai.core.client')
    def test_ping_openai_failure(self, mock_client):
        """Тест неудачного ping OpenAI"""
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        result = ping_openai()
        assert result is False

class TestAIGenerate:
    """Тесты для функции ai_generate"""
    
    @pytest.mark.asyncio
    async def test_ai_generate_fallback_error_ru(self):
        """Тест fallback_error на русском"""
        result = await ai_generate('fallback_error', target_language='ru')
        assert result == "Извините, произошла ошибка. Попробуйте ещё раз."
    
    @pytest.mark.asyncio
    async def test_ai_generate_fallback_error_en(self):
        """Тест fallback_error на английском"""
        result = await ai_generate('fallback_error', target_language='en')
        assert result == "Sorry, an error occurred. Please try again."
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.client')
    @patch('src.bot.ai.core.get_prompt')
    async def test_ai_generate_restaurant_recommendation(self, mock_get_prompt, mock_client):
        """Тест генерации рекомендации ресторана"""
        mock_get_prompt.return_value = "Test prompt"
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test response"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = await ai_generate('restaurant_recommendation', target_language='ru', preferences='sea food')
        
        assert result == "Test response"
        mock_get_prompt.assert_called_once()
        mock_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ai_generate_unknown_task(self):
        """Тест неизвестной задачи"""
        result = await ai_generate('unknown_task', target_language='ru')
        assert result == "Извините, произошла ошибка. Попробуйте ещё раз."

class TestAsk:
    """Тесты для функции ask"""
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.ai_generate')
    async def test_ask_success(self, mock_ai_generate):
        """Тест успешного вопроса"""
        mock_ai_generate.return_value = "Test answer"
        
        answer, chat_log = await ask("Test question", language='en')
        
        assert answer == "Test answer"
        assert chat_log == []
        mock_ai_generate.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.ai_generate')
    async def test_ask_with_chat_log(self, mock_ai_generate):
        """Тест вопроса с историей чата"""
        mock_ai_generate.return_value = "Test answer"
        initial_log = [{'question': 'prev', 'answer': 'prev_ans'}]
        
        answer, chat_log = await ask("Test question", chat_log=initial_log, language='ru')
        
        assert answer == "Test answer"
        assert chat_log == initial_log

class TestDetectAreaFromText:
    """Тесты для функции detect_area_from_text"""
    
    @pytest.mark.asyncio
    async def test_detect_patong(self):
        """Тест определения Патонга"""
        result = await detect_area_from_text("Я хочу поехать в Патонг", 'ru')
        assert result == 'patong'
    
    @pytest.mark.asyncio
    async def test_detect_kata_english(self):
        """Тест определения Kata на английском"""
        result = await detect_area_from_text("I want to go to Kata Beach", 'en')
        assert result == 'kata'
    
    @pytest.mark.asyncio
    async def test_detect_unknown_area(self):
        """Тест неизвестной области"""
        result = await detect_area_from_text("Я хочу в Марс", 'ru')
        assert result is None
    
    @pytest.mark.asyncio
    async def test_detect_chalong_alias(self):
        """Тест определения Чалонга через алиас"""
        result = await detect_area_from_text("чалонг", 'ru')
        assert result == 'chalong'

class TestIsAboutRestaurants:
    """Тесты для функции is_about_restaurants"""
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.client')
    async def test_is_about_restaurants_positive(self, mock_client):
        """Тест определения вопроса о ресторанах"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "restaurant"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = await is_about_restaurants("Где поесть мясо?")
        assert result is True
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.client')
    async def test_is_about_restaurants_negative(self, mock_client):
        """Тест определения отвлеченного вопроса"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "general"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = await is_about_restaurants("Какая сегодня погода?")
        assert result is False
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.client')
    async def test_is_about_restaurants_error(self, mock_client):
        """Тест ошибки в определении типа вопроса"""
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = await is_about_restaurants("Тестовый вопрос")
        assert result is False

class TestGeneralChat:
    """Тесты для функции general_chat"""
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.client')
    async def test_general_chat_success(self, mock_client):
        """Тест успешного общего чата"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Интересно! А кстати, знаете где вкусно поесть?"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = await general_chat("Какая погода?", 'ru')
        assert "Интересно!" in result
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.client')
    @patch('src.bot.ai.translation.translate_message')
    async def test_general_chat_error(self, mock_translate, mock_client):
        """Тест ошибки в общем чате"""
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_translate.return_value = "Ошибка"
        
        result = await general_chat("Тест", 'ru')
        assert result == "Ошибка"

class TestRestaurantChat:
    """Тесты для функции restaurant_chat"""
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.client')
    @patch('src.bot.ai.core.get_relevant_restaurant_data')
    async def test_restaurant_chat_success(self, mock_get_data, mock_client):
        """Тест успешного чата о ресторанах"""
        mock_get_data.return_value = "Restaurant: Test Restaurant"
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Отличный ресторан!"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = await restaurant_chat("Расскажите об этом ресторане", "Test info", 'ru')
        assert result == "Отличный ресторан!"
    
    @pytest.mark.asyncio
    async def test_restaurant_chat_error(self):
        """Тест ошибки в чате о ресторанах"""
        with patch('src.bot.ai.core.client') as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("API Error")
            
            result = await restaurant_chat("Тест", "info", 'ru')
            assert "ошибка" in result.lower()

class TestGetRelevantRestaurantData:
    """Тесты для функции get_relevant_restaurant_data"""
    
    @pytest.mark.asyncio
    async def test_get_relevant_data_success(self):
        """Тест получения релевантных данных"""
        restaurants = [
            {'name': 'Test Restaurant', 'cuisine': 'Italian', 'average_check': '$$'},
            {'name': 'Another Restaurant', 'cuisine': 'Thai', 'average_check': '$$$'}
        ]
        
        result = await get_relevant_restaurant_data("Where to eat?", restaurants, 'en')
        
        assert "Test Restaurant" in result
        assert "Italian" in result
        assert "Another Restaurant" in result
    
    @pytest.mark.asyncio
    async def test_get_relevant_data_empty(self):
        """Тест с пустым списком ресторанов"""
        result = await get_relevant_restaurant_data("Test", [], 'en')
        assert result == ""
    
    @pytest.mark.asyncio
    @patch('src.bot.ai.core.logger')
    async def test_get_relevant_data_error(self, mock_logger):
        """Тест ошибки при получении данных"""
        # Создаем объект, который вызовет ошибку при обращении к .get()
        class BadDict:
            def get(self, key, default=None):
                raise Exception("Simulated error")
                
        restaurants = [BadDict()]
        
        result = await get_relevant_restaurant_data("Test", restaurants, 'en')
        assert result == "No restaurant data available"
        mock_logger.error.assert_called_once() 