#!/usr/bin/env python3
import asyncio
import psycopg2
from psycopg2.extras import DictCursor
import sys
import os

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from context_processor import get_relevant_restaurant_data

async def test_ai_processor():
    """Тестирует AI-контекстный процессор с различными вопросами"""
    
    try:
        # Подключаемся к PostgreSQL
        conn = psycopg2.connect(
            dbname="booktable",
            user="root",
            host="/var/run/postgresql"
        )
        
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Получаем данные WeCafe для тестов
        cur.execute("SELECT * FROM restaurants WHERE name ILIKE '%WeCafe%' LIMIT 1")
        result = cur.fetchone()
        
        if not result:
            print("❌ WeCafe не найден в базе данных")
            return
            
        restaurant_data = dict(result)
        restaurants = [restaurant_data]
        
        print("🔍 ТЕСТИРОВАНИЕ AI-КОНТЕКСТНОГО ПРОЦЕССОРА")
        print("=" * 60)
        print(f"Ресторан: {restaurant_data['name']}")
        print(f"Всего полей в БД: {len(restaurant_data)}")
        print()
        
        # Тестовые вопросы
        test_questions = [
            "а есть там мясо?",
            "знаменитости посещают?", 
            "есть ли детское меню?",
            "какое вино?",
            "во сколько работает?",
            "есть ли веганские блюда?",
            "можно ли сидеть на улице?",
            "принимают ли карты?"
        ]
        
        total_original_chars = 0
        total_optimized_chars = 0
        
        for i, question in enumerate(test_questions, 1):
            print(f"📝 ТЕСТ {i}: {question}")
            print("-" * 40)
            
            # Получаем оригинальные данные (все поля)
            original_data = ""
            for key, value in restaurant_data.items():
                if value and str(value).strip() and str(value).strip().lower() not in ['none', 'null', '']:
                    original_data += f"{key.replace('_', ' ').title()}: {value}\n"
            
            # Получаем оптимизированные данные через AI
            optimized_data = await get_relevant_restaurant_data(question, restaurants, 'ru')
            
            original_chars = len(original_data)
            optimized_chars = len(optimized_data)
            savings = ((original_chars - optimized_chars) / original_chars * 100) if original_chars > 0 else 0
            
            total_original_chars += original_chars
            total_optimized_chars += optimized_chars
            
            print(f"Оригинал: {original_chars} символов")
            print(f"Оптимизировано: {optimized_chars} символов")
            print(f"Экономия: {savings:.1f}%")
            
            # Проверяем ключевые поля
            key_fields_found = []
            if "key_dishes" in optimized_data.lower():
                key_fields_found.append("key_dishes")
            if "celebrity" in optimized_data.lower() or "notable" in optimized_data.lower():
                key_fields_found.append("celebrity_info")
            if "working" in optimized_data.lower() or "hours" in optimized_data.lower():
                key_fields_found.append("working_hours")
            if "wine" in optimized_data.lower() or "cocktail" in optimized_data.lower():
                key_fields_found.append("drinks")
            
            if key_fields_found:
                print(f"✅ Найдены релевантные поля: {', '.join(key_fields_found)}")
            else:
                print("⚠️  Релевантные поля не обнаружены")
            
            print()
        
        # Общая статистика
        total_savings = ((total_original_chars - total_optimized_chars) / total_original_chars * 100) if total_original_chars > 0 else 0
        
        print("📊 ОБЩАЯ СТАТИСТИКА")
        print("=" * 60)
        print(f"Всего тестов: {len(test_questions)}")
        print(f"Общий объем оригинальных данных: {total_original_chars:,} символов")
        print(f"Общий объем оптимизированных данных: {total_optimized_chars:,} символов")
        print(f"Средняя экономия токенов: {total_savings:.1f}%")
        
        if total_savings > 70:
            print("🎉 ОТЛИЧНО! AI-процессор работает эффективно")
        elif total_savings > 50:
            print("✅ ХОРОШО! AI-процессор показывает приемлемые результаты")
        else:
            print("⚠️  ВНИМАНИЕ! Низкая эффективность AI-процессора")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_ai_processor()) 