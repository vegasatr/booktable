#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
АНАЛИЗ МЫШЛЕНИЯ AI В ДИАЛОГАХ
=============================

Этот модуль предназначен для изучения и анализа поведения AI бота в диалогах.
Позволяет тестировать различные сценарии разговоров и понимать логику принятия решений.

Используется для:
- Изучения логики принятия решений AI
- Оптимизации промптов для более человечного поведения  
- Тестирования сценариев диалогов
- Анализа качества ответов бота

ЗАПУСК: python tests/manual/dialogue_studies/ai_thinking_analysis.py
"""

import sys
import os
import asyncio

# Добавляем корень проекта в PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from openai import OpenAI

# Настройка OpenAI
openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

async def analyze_dialogue_decision(conversation_history, budget="$$"):
    """
    Анализирует историю диалога и принимает решение: продолжать диалог или искать рестораны
    Имитирует логику из main.py функции talk()
    """
    try:
        # Формируем контекст разговора - ВЕСЬ диалог, включая ответы бота
        conversation_context = []
        for msg in conversation_history:
            if msg['role'] == 'user':
                conversation_context.append(f"Клиент: {msg['content']}")
            elif msg['role'] == 'assistant':
                conversation_context.append(f"Бот: {msg['content']}")
        
        full_context = '\n'.join(conversation_context)
        
        # Системный промпт для анализа диалога
        decision_prompt = f"""Ты опытный консультант по ресторанам Пхукета. Ведешь живую беседу с клиентом.

КОНТЕКСТ ДИАЛОГА:
{full_context}

Бюджет клиента: {budget}

ЗАДАЧА: Проанализируй диалог и реши - достаточно ли информации для поиска ресторанов?

КРИТЕРИИ ДЛЯ ПОИСКА:
✅ Есть тип кухни/еды + контекст (атмосфера, повод, компания)
✅ Конкретный тип заведения + детали
✅ Достаточно информации для понимания потребностей

Если готов к поиску - ответь "ПОИСК"
Если нет - задай умный вопрос для уточнения

Отвечай естественно на русском языке."""

        last_user_message = ""
        for msg in reversed(conversation_history):
            if msg['role'] == 'user':
                last_user_message = msg['content']
                break
        
        messages = [
            {"role": "system", "content": decision_prompt},
            {"role": "user", "content": last_user_message}
        ]
        
        response = client.chat.completions.create(
            model=openai_model,
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        
        ai_response = response.choices[0].message.content.strip()
        should_search = "ПОИСК" in ai_response
        
        return {
            "should_search": should_search,
            "ai_response": ai_response,
            "conversation_context": full_context
        }
        
    except Exception as e:
        print(f"❌ Ошибка в анализе AI: {e}")
        return {
            "should_search": False,
            "ai_response": "Расскажите больше о ваших предпочтениях",
            "conversation_context": full_context if 'full_context' in locals() else ""
        }

async def test_dialogue_scenario(scenario):
    """Тестирует один сценарий диалога"""
    print(f"\n🎭 СЦЕНАРИЙ: {scenario['name']}")
    print("=" * 60)
    
    conversation_history = []
    
    for i, turn in enumerate(scenario['turns'], 1):
        print(f"\nШаг {i}:")
        
        if turn['type'] == 'user':
            # Добавляем сообщение пользователя
            conversation_history.append({"role": "user", "content": turn['message']})
            print(f"👤 Пользователь: {turn['message']}")
            
            # AI анализирует и принимает решение
            analysis = await analyze_dialogue_decision(conversation_history, scenario.get('budget', '$$'))
            
            if analysis['should_search']:
                print(f"🤖 Решение: ПОИСК РЕСТОРАНОВ")
                print(f"💭 Обоснование: {analysis['ai_response']}")
                
                # Проверяем корректность решения
                expected = turn.get('expected_decision', 'continue')
                if expected == 'search':
                    print("✅ ПРАВИЛЬНО - пора искать!")
                    return "success"
                else:
                    print("❌ СЛИШКОМ РАНО - нужно больше информации")
                    return "too_early"
            else:
                print(f"🤖 Продолжение диалога: {analysis['ai_response']}")
                conversation_history.append({"role": "assistant", "content": analysis['ai_response']})
                
                # Проверяем, не поздно ли
                expected = turn.get('expected_decision', 'continue')
                if expected == 'search':
                    print("❌ СЛИШКОМ ПОЗДНО - должен был уже искать!")
                    return "too_late"
        
        elif turn['type'] == 'bot':
            # Заранее определенный ответ бота
            conversation_history.append({"role": "assistant", "content": turn['message']})
            print(f"🤖 Бот: {turn['message']}")
    
    return "incomplete"

# Тестовые сценарии для анализа
TEST_SCENARIOS = [
    {
        "name": "Быстрый конкретный запрос - суши",
        "budget": "$$", 
        "turns": [
            {"type": "user", "message": "ищу суши-бар в центре для двоих", "expected_decision": "search"}
        ]
    },
    {
        "name": "Романтическое свидание - пошаговое выяснение",
        "budget": "$$$",
        "turns": [
            {"type": "user", "message": "хочу на романтическое свидание", "expected_decision": "continue"},
            {"type": "user", "message": "итальянскую кухню, красивое место", "expected_decision": "search"}
        ]
    },
    {
        "name": "Семейный обед - нужны детали",
        "budget": "$$",
        "turns": [
            {"type": "user", "message": "с семьей и детьми поесть", "expected_decision": "continue"},
            {"type": "user", "message": "что-то европейское, не острое", "expected_decision": "search"}
        ]
    },
    {
        "name": "Неконкретный запрос - требует уточнений",
        "budget": "$$",
        "turns": [
            {"type": "user", "message": "хочу поесть", "expected_decision": "continue"},
            {"type": "user", "message": "что-то вкусное", "expected_decision": "continue"},
            {"type": "user", "message": "мясное, для компании друзей", "expected_decision": "search"}
        ]
    }
]

async def run_dialogue_analysis():
    """Запускает анализ всех тестовых сценариев"""
    print("🧠 АНАЛИЗ МЫШЛЕНИЯ AI В ДИАЛОГАХ")
    print("=" * 80)
    
    results = {"success": 0, "too_early": 0, "too_late": 0, "incomplete": 0}
    
    for scenario in TEST_SCENARIOS:
        result = await test_dialogue_scenario(scenario)
        results[result] += 1
        
        print(f"\n📊 Результат: {result.upper()}")
        print("-" * 40)
    
    print(f"\n📈 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"✅ Успешно: {results['success']}")
    print(f"⚡ Слишком рано: {results['too_early']}")  
    print(f"🐌 Слишком поздно: {results['too_late']}")
    print(f"❓ Незавершено: {results['incomplete']}")
    
    total = sum(results.values())
    success_rate = (results['success'] / total * 100) if total > 0 else 0
    print(f"\n🎯 Точность принятия решений: {success_rate:.1f}%")

if __name__ == "__main__":
    asyncio.run(run_dialogue_analysis()) 