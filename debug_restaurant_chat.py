#!/usr/bin/env python3
import asyncio
import psycopg2
from psycopg2.extras import DictCursor
import sys
import os

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import restaurant_chat

class MockContext:
    def __init__(self, restaurants=None):
        self.user_data = {'restaurants': restaurants or []}

async def test_restaurant_chat():
    """Тестирует функцию restaurant_chat с реальными данными"""
    
    try:
        # Подключаемся к PostgreSQL
        conn = psycopg2.connect(
            dbname="booktable",
            user="root",
            host="/var/run/postgresql"
        )
        
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Получаем данные WeCafe
        cur.execute("SELECT * FROM restaurants WHERE name ILIKE '%WeCafe%' LIMIT 1")
        result = cur.fetchone()
        
        if not result:
            print("❌ WeCafe не найден в базе данных")
            return
            
        restaurant_data = dict(result)
        restaurants = [restaurant_data]
        
        print(f"✅ Найден ресторан: {restaurant_data['name']}")
        print(f"📊 Всего полей в ресторане: {len(restaurant_data)}")
        
        # Создаем mock контекст с ресторанами
        context_with_restaurants = MockContext(restaurants)
        context_without_restaurants = MockContext([])
        
        question = "а есть там мясо?"
        
        # Формируем базовую информацию о ресторане (как в старой версии)
        basic_info = f"Restaurant: {restaurant_data['name']}\nCuisine: {restaurant_data.get('cuisine', 'N/A')}\nFeatures: {restaurant_data.get('features', 'N/A')}"
        
        print("\n" + "="*60)
        print("ТЕСТ 1: С ресторанами в контексте (должен использовать AI)")
        print("="*60)
        
        response1 = await restaurant_chat(question, basic_info, 'ru', context_with_restaurants)
        print(f"Ответ: {response1}")
        
        print("\n" + "="*60)
        print("ТЕСТ 2: Без ресторанов в контексте (fallback к базовой информации)")
        print("="*60)
        
        response2 = await restaurant_chat(question, basic_info, 'ru', context_without_restaurants)
        print(f"Ответ: {response2}")
        
        print("\n" + "="*60)
        print("ТЕСТ 3: Без контекста вообще")
        print("="*60)
        
        response3 = await restaurant_chat(question, basic_info, 'ru', None)
        print(f"Ответ: {response3}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_restaurant_chat()) 