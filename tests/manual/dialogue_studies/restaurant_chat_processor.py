#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ТЕСТИРОВАНИЕ КОНТЕКСТНОГО ПРОЦЕССОРА РЕСТОРАНОВ
===============================================

Модуль для изучения работы AI-powered контекстного процессора.
Анализирует как AI выбирает релевантные поля из базы данных ресторанов.

Используется для:
- Оптимизации AI-процессора контекста
- Тестирования релевантности выбранных данных
- Изучения эффективности сжатия информации
- Анализа качества ответов на основе контекста

ЗАПУСК: python tests/manual/dialogue_studies/restaurant_chat_processor.py
"""

import sys
import os
import asyncio

# Добавляем корень проекта в PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

# Тестовые данные ресторанов для эксперименте
SAMPLE_RESTAURANTS = [
    {
        'name': 'Acqua Restaurant',
        'cuisine': 'Итальянская, Европейская',
        'area': 'patong',
        'address': 'Kalim Beach, Патонг',
        'phone': '+66 76 302 324',
        'average_check': '$$$',
        'rating': 4.5,
        'features': ['Вид на море', 'Романтическая атмосфера', 'Винная карта', 'Парковка'],
        'description': 'Элегантный ресторан с потрясающим видом на море. Идеально для романтических ужинов.',
        'working_hours': '18:00-23:00',
        'popular_dishes': ['Ризотто с морепродуктами', 'Стейк из тунца', 'Тирамису']
    },
    {
        'name': 'Blue Elephant Phuket',
        'cuisine': 'Тайская',
        'area': 'phuket_town',
        'address': '96 Krabi Road, Пхукет Таун',
        'phone': '+66 76 354 355',
        'average_check': '$$$$',
        'rating': 4.8,
        'features': ['Историческое здание', 'Традиционная атмосфера', 'Кулинарные мастер-классы'],
        'description': 'Премиальный тайский ресторан в историческом особняке. Изысканная тайская кухня.',
        'working_hours': '11:30-14:30, 18:30-22:30',
        'popular_dishes': ['Том ям с омарами', 'Массаман карри', 'Манго с клейким рисом']
    },
    {
        'name': 'La Gritta',
        'cuisine': 'Итальянская',
        'area': 'patong',
        'address': 'Amari Phuket, Патонг Бич',
        'phone': '+66 76 340 106',
        'average_check': '$$$',
        'rating': 4.3,
        'features': ['Пляжная локация', 'Итальянский шеф-повар', 'Семейная атмосфера'],
        'description': 'Аутентичная итальянская кухня прямо на пляже Патонг.',
        'working_hours': '18:00-23:00',
        'popular_dishes': ['Пицца Маргарита', 'Паста Карбонара', 'Джелато']
    },
    {
        'name': 'Kan Eang @ Pier',
        'cuisine': 'Морепродукты, Тайская',
        'area': 'chalong',
        'address': 'Chalong Pier, Чалонг',
        'phone': '+66 76 381 323',
        'average_check': '$$',
        'rating': 4.4,
        'features': ['Вид на марину', 'Свежие морепродукты', 'Местная атмосфера', 'Парковка'],
        'description': 'Популярный ресторан морепродуктов с видом на пристань Чалонг.',
        'working_hours': '10:00-22:00',
        'popular_dishes': ['Омар на гриле', 'Том ям с креветками', 'Жареный краб']
    }
]

async def test_context_processor_relevance():
    """Тестирует релевантность AI-процессора контекста"""
    
    # Импортируем функцию из проекта
    from src.bot.ai.core import get_relevant_restaurant_data
    
    test_cases = [
        {
            "question": "Где поесть романтично на ужин?",
            "expected_restaurants": ["Acqua Restaurant"],
            "expected_features": ["романтическая", "вид на море"],
            "not_expected": ["семейная", "мастер-классы"]
        },
        {
            "question": "Ищу аутентичную тайскую кухню",
            "expected_restaurants": ["Blue Elephant Phuket"],
            "expected_features": ["тайская", "традиционная"],
            "not_expected": ["итальянская", "пицца"]
        },
        {
            "question": "Семейный ужин на пляже с детьми",
            "expected_restaurants": ["La Gritta"],
            "expected_features": ["семейная", "пляж"],
            "not_expected": ["премиальный", "изысканная"]
        },
        {
            "question": "Свежие морепродукты, местное место",
            "expected_restaurants": ["Kan Eang @ Pier"],
            "expected_features": ["морепродукты", "местная"],
            "not_expected": ["итальянский", "винная карта"]
        }
    ]
    
    print("🔍 ТЕСТ РЕЛЕВАНТНОСТИ КОНТЕКСТНОГО ПРОЦЕССОРА")
    print("=" * 80)
    
    total_score = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}: {test_case['question']}")
        print("-" * 60)
        
        # Получаем оптимизированные данные от AI
        optimized_data = await get_relevant_restaurant_data(
            test_case['question'], 
            SAMPLE_RESTAURANTS, 
            'ru'
        )
        
        print(f"📊 AI выбрал данные ({len(optimized_data)} символов):")
        print(optimized_data[:300] + "..." if len(optimized_data) > 300 else optimized_data)
        
        # Анализируем релевантность
        score = 0
        max_score = len(test_case['expected_restaurants']) + len(test_case['expected_features'])
        
        # Проверяем ожидаемые рестораны
        for restaurant in test_case['expected_restaurants']:
            if restaurant.lower() in optimized_data.lower():
                score += 1
                print(f"✅ Найден ожидаемый ресторан: {restaurant}")
            else:
                print(f"❌ Не найден ожидаемый ресторан: {restaurant}")
        
        # Проверяем ожидаемые особенности
        for feature in test_case['expected_features']:
            if feature.lower() in optimized_data.lower():
                score += 1
                print(f"✅ Найдена ожидаемая особенность: {feature}")
            else:
                print(f"❌ Не найдена ожидаемая особенность: {feature}")
        
        # Проверяем что нежелательное не попало
        unwanted_found = []
        for unwanted in test_case['not_expected']:
            if unwanted.lower() in optimized_data.lower():
                unwanted_found.append(unwanted)
        
        if unwanted_found:
            print(f"⚠️  Найдены нежелательные элементы: {unwanted_found}")
        else:
            print("✅ Нежелательные элементы отфильтрованы")
        
        test_score = (score / max_score) * 100 if max_score > 0 else 0
        total_score += test_score
        
        print(f"📊 Оценка релевантности: {test_score:.1f}%")
    
    avg_score = total_score / len(test_cases)
    print(f"\n🎯 ОБЩАЯ ОЦЕНКА РЕЛЕВАНТНОСТИ: {avg_score:.1f}%")
    
    if avg_score >= 80:
        print("🏆 ОТЛИЧНО - AI эффективно выбирает релевантные данные")
    elif avg_score >= 60:
        print("✅ ХОРОШО - AI в целом справляется с задачей")
    else:
        print("⚠️  ТРЕБУЕТ УЛУЧШЕНИЯ - нужно оптимизировать промпты")

async def analyze_compression_efficiency():
    """Анализирует эффективность сжатия данных AI процессором"""
    
    from src.bot.ai.core import get_relevant_restaurant_data
    
    print(f"\n📈 АНАЛИЗ ЭФФЕКТИВНОСТИ СЖАТИЯ ДАННЫХ")
    print("=" * 80)
    
    # Считаем размер исходных данных
    original_size = 0
    for restaurant in SAMPLE_RESTAURANTS:
        restaurant_text = f"""
Ресторан: {restaurant['name']}
Кухня: {restaurant['cuisine']}
Район: {restaurant['area']}
Адрес: {restaurant['address']}
Телефон: {restaurant['phone']}
Средний чек: {restaurant['average_check']}
Рейтинг: {restaurant['rating']}
Особенности: {', '.join(restaurant['features'])}
Описание: {restaurant['description']}
Часы работы: {restaurant['working_hours']}
Популярные блюда: {', '.join(restaurant['popular_dishes'])}
"""
        original_size += len(restaurant_text)
    
    test_questions = [
        "Романтичный ужин для двоих",
        "Семейный обед с детьми", 
        "Деловая встреча в центре",
        "Местная тайская кухня"
    ]
    
    compression_ratios = []
    
    for question in test_questions:
        optimized_data = await get_relevant_restaurant_data(question, SAMPLE_RESTAURANTS, 'ru')
        optimized_size = len(optimized_data)
        
        compression_ratio = (1 - optimized_size / original_size) * 100
        compression_ratios.append(compression_ratio)
        
        print(f"❓ Вопрос: {question}")
        print(f"📏 Исходный размер: {original_size} символов")
        print(f"📏 Сжатый размер: {optimized_size} символов")
        print(f"📊 Сжатие: {compression_ratio:.1f}%")
        print("-" * 40)
    
    avg_compression = sum(compression_ratios) / len(compression_ratios)
    print(f"\n🗜️  СРЕДНЕЕ СЖАТИЕ: {avg_compression:.1f}%")
    
    if avg_compression >= 70:
        print("🚀 ОТЛИЧНО - высокая эффективность сжатия")
    elif avg_compression >= 50:
        print("✅ ХОРОШО - умеренное сжатие")
    else:
        print("⚠️  СЛАБОЕ СЖАТИЕ - возможно слишком много данных")

async def run_processor_tests():
    """Запускает все тесты процессора"""
    await test_context_processor_relevance()
    await analyze_compression_efficiency()

if __name__ == "__main__":
    asyncio.run(run_processor_tests()) 