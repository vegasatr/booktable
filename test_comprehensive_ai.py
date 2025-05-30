#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI

# Настройка OpenAI
openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

async def analyze_dialogue_decision(conversation_history, budget="$$"):
    """
    Анализирует историю диалога и принимает решение: продолжать диалог или искать рестораны
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
        
        # Системный промпт с улучшенными критериями
        decision_prompt = f"""Ты опытный консультант по ресторанам Пхукета. Ведешь живую беседу с клиентом, чтобы понять его предпочтения.

КОНТЕКСТ:
- Бюджет клиента уже известен: {budget}
- ПОЛНАЯ история разговора:
{full_context}

ТВОЯ ЗАДАЧА:
1. ПРОАНАЛИЗИРУЙ ВСЮ историю разговора и сделай УМНЫЕ ВЫВОДЫ о предпочтениях клиента
2. Если информации ДОСТАТОЧНО для поиска 1-3 конкретных ресторанов - ответь "ПОИСК"
3. Если нет - веди живую беседу, задавая ТОЛЬКО полезные вопросы

ПРИНЦИПЫ АНАЛИЗА:
🧠 ДУМАЙ как человек - что клиент РЕАЛЬНО имеет в виду?
🧠 ДЕЛАЙ ВЫВОДЫ из контекста - если упоминает детей, семью, свидание, работу - что это означает для атмосферы?
🧠 ПОНИМАЙ подтекст - "рабочий обед" = деловая атмосфера, "день рождения" = праздничная, "с детьми" = семейная
🧠 НЕ требуй прямых слов - анализируй СМЫСЛ сказанного
🧠 УЧИТЫВАЙ предыдущие ответы бота - не повторяй уже заданные вопросы
🧠 РАЗВИВАЙ диалог логично - каждый вопрос должен углублять понимание

КРИТЕРИЙ ДЛЯ ПОИСКА:
Если ты можешь ПОНЯТЬ из разговора:
- Тип кухни/еды + любую информацию об атмосфере/локации/особенностях
- ИЛИ достаточно специфичный запрос (например: "суши-бар в центре для двоих")
- ИЛИ клиент дал достаточно деталей для понимания его потребностей
- ИЛИ упомянул конкретный тип заведения + контекст (кто идет, зачем)

ПРИМЕРЫ ГОТОВНОСТИ К ПОИСКУ:
✅ "итальянскую кухню на свидание" = ТИП КУХНИ + АТМОСФЕРА
✅ "мясное с детьми" = ТИП ЕДЫ + АТМОСФЕРА  
✅ "суши-бар в центре для двоих" = КОНКРЕТНОЕ ЗАВЕДЕНИЕ + КОНТЕКСТ
✅ "европейскую, тихое место для деловой встречи" = КУХНЯ + АТМОСФЕРА + ЦЕЛЬ
❌ "с друзьями повеселиться" = ТОЛЬКО АТМОСФЕРА, НЕТ ТИПА КУХНИ/ЕДЫ

ВАЖНО:
- НЕ создавай жесткие правила - ДУМАЙ над каждым случаем
- НЕ спрашивай о деталях приготовления (прожарка, способы готовки)
- НЕ задавай повторные вопросы, если информация уже понятна из контекста
- БУДЬ решительным - лучше начать поиск, чем затягивать диалог
- АНАЛИЗИРУЙ весь контекст, а не только последнее сообщение
- ПОМНИ что уже спрашивал бот - не повторяйся

Отвечай естественно на русском языке. Обращайся на "Вы"."""

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
        print(f"Error in AI analysis: {e}")
        return {
            "should_search": False,
            "ai_response": "Расскажите больше о ваших предпочтениях",
            "conversation_context": full_context if 'full_context' in locals() else ""
        }

async def simulate_realistic_dialogue(scenario):
    """Симулирует реалистичный диалог с развитием разговора"""
    print(f"\n🎭 Сценарий: {scenario['name']}")
    print("=" * 60)
    
    conversation_history = []
    step = 1
    
    for turn in scenario['turns']:
        print(f"\nШаг {step}:")
        
        if turn['type'] == 'user':
            conversation_history.append({"role": "user", "content": turn['message']})
            print(f"👤 Пользователь: {turn['message']}")
            
            analysis = await analyze_dialogue_decision(conversation_history, scenario.get('budget', '$$'))
            
            if analysis['should_search']:
                print(f"🤖 Бот решил: ПОИСК РЕСТОРАНОВ")
                print(f"💭 AI ответ: {analysis['ai_response']}")
                
                expected_decision = turn.get('expected_decision', 'continue')
                if expected_decision == 'search':
                    print("✅ ПРАВИЛЬНОЕ РЕШЕНИЕ - пора искать!")
                    return True
                else:
                    print("❌ СЛИШКОМ РАНО - нужно больше информации")
                    return False
            else:
                print(f"🤖 Бот продолжает диалог: {analysis['ai_response']}")
                conversation_history.append({"role": "assistant", "content": analysis['ai_response']})
                
                expected_decision = turn.get('expected_decision', 'continue')
                if expected_decision == 'search':
                    print("❌ СЛИШКОМ ПОЗДНО - должен был уже искать!")
                    return False
        
        elif turn['type'] == 'bot':
            conversation_history.append({"role": "assistant", "content": turn['message']})
            print(f"🤖 Бот: {turn['message']}")
        
        step += 1
    
    final_expected = scenario.get('final_expected', 'search')
    if final_expected == 'search':
        print("❌ ДИАЛОГ НЕ ЗАВЕРШЕН - должен был начать поиск")
        return False
    else:
        print("✅ ДИАЛОГ КОРРЕКТНО ПРОДОЛЖАЕТСЯ")
        return True

async def run_comprehensive_tests():
    """Запускает комплексные тесты с 50 сценариями"""
    
    scenarios = [
        # === БЫСТРЫЕ СЦЕНАРИИ (1-2 вопроса) ===
        {
            "name": "Конкретный запрос - суши для двоих",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "ищу суши-бар в центре города для двоих", "expected_decision": "search"}
            ]
        },
        {
            "name": "Конкретный запрос - итальянский ресторан на свидание",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "нужен итальянский ресторан на романтическое свидание", "expected_decision": "search"}
            ]
        },
        {
            "name": "Конкретный запрос - стейкхаус для деловой встречи",
            "budget": "$$$$",
            "turns": [
                {"type": "user", "message": "ищу стейкхаус для деловой встречи, тихое место", "expected_decision": "search"}
            ]
        },
        {
            "name": "Конкретный запрос - тайская кухня с детьми",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу тайскую кухню, идем с детьми", "expected_decision": "search"}
            ]
        },
        {
            "name": "Конкретный запрос - морепродукты у моря",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "ищу ресторан морепродуктов с видом на море", "expected_decision": "search"}
            ]
        },
        
        # === СРЕДНИЕ СЦЕНАРИИ (2-3 вопроса) ===
        {
            "name": "Романтическое свидание - уточнение кухни",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "ищу ресторан на свидание", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете для романтического вечера?"},
                {"type": "user", "message": "итальянскую, с видом на море", "expected_decision": "search"}
            ]
        },
        {
            "name": "Семейный ужин - уточнение атмосферы",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу поужинать с семьей", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "что-то мясное, и чтобы детям было интересно", "expected_decision": "search"}
            ]
        },
        {
            "name": "Деловой обед - быстрое уточнение",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "нужен ресторан для деловой встречи", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "европейскую, тихое место", "expected_decision": "search"}
            ]
        },
        {
            "name": "Празднование дня рождения",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "празднуем день рождения", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете и сколько человек будет?"},
                {"type": "user", "message": "азиатскую, нас будет 6 человек", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ужин с друзьями - быстрое решение",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "ужин с друзьями, хотим повеселиться", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "морепродукты и чтобы музыка была", "expected_decision": "search"}
            ]
        },
        {
            "name": "Завтрак/бранч",
            "budget": "$",
            "turns": [
                {"type": "user", "message": "ищу место для бранча", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "европейскую, с хорошим кофе", "expected_decision": "search"}
            ]
        },
        {
            "name": "Поздний ужин",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "нужно место, которое работает допоздна", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню ищете?"},
                {"type": "user", "message": "азиатскую, и чтобы после 23:00 работали", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с развлечениями",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу ресторан где есть шоу", "expected_decision": "continue"},
                {"type": "bot", "message": "Какое шоу интересует и какая кухня?"},
                {"type": "user", "message": "тайские танцы и тайская кухня", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан у пляжа",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу поесть прямо на пляже", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "морепродукты, свежую рыбу", "expected_decision": "search"}
            ]
        },
        {
            "name": "Быстрый обед",
            "budget": "$",
            "turns": [
                {"type": "user", "message": "нужно быстро пообедать", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "что-то простое, тайскую уличную еду", "expected_decision": "search"}
            ]
        },
        
        # === РАЗВЕРНУТЫЕ СЦЕНАРИИ (3-4 вопроса) ===
        {
            "name": "Неопределенный клиент - постепенное выяснение",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу поесть", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "не знаю, что-то вкусное", "expected_decision": "continue"},
                {"type": "bot", "message": "А какая компания будет?"},
                {"type": "user", "message": "с женой, хотим романтично", "expected_decision": "search"}
            ]
        },
        {
            "name": "Выбор между кухнями",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "хочу что-то особенное", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню рассматриваете?"},
                {"type": "user", "message": "думаю между японской и французской", "expected_decision": "continue"},
                {"type": "bot", "message": "А какой повод для ужина?"},
                {"type": "user", "message": "годовщина свадьбы, хочется изысканно", "expected_decision": "search"}
            ]
        },
        {
            "name": "Туристы - изучение локальной кухни",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "мы туристы, хотим попробовать местную кухню", "expected_decision": "continue"},
                {"type": "bot", "message": "Интересуетесь тайской кухней или чем-то еще?"},
                {"type": "user", "message": "да, тайская звучит интересно", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая атмосфера вам нужна?"},
                {"type": "user", "message": "аутентичная, но не слишком острая еда", "expected_decision": "search"}
            ]
        },
        {
            "name": "Корпоративный ужин",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "организую корпоративный ужин", "expected_decision": "continue"},
                {"type": "bot", "message": "Сколько человек и какие предпочтения по кухне?"},
                {"type": "user", "message": "человек 12, нужно что-то универсальное", "expected_decision": "continue"},
                {"type": "bot", "message": "Европейская или азиатская кухня подойдет?"},
                {"type": "user", "message": "европейская лучше, и чтобы можно было презентацию провести", "expected_decision": "search"}
            ]
        },
        {
            "name": "Вегетарианские предпочтения",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "ищу ресторан с вегетарианскими блюдами", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "индийскую или средиземноморскую", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая атмосфера нужна?"},
                {"type": "user", "message": "спокойная, для двоих", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с семейной атмосферой",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "ищу семейный ресторан", "expected_decision": "continue"},
                {"type": "bot", "message": "Какие требования к детской зоне?"},
                {"type": "user", "message": "чтобы дети могли играть, а мы спокойно поесть", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "интернациональную, чтобы всем понравилось", "expected_decision": "search"}
            ]
        },
        {
            "name": "Винный ужин",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "хочу ресторан с хорошей винной картой", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "французскую, и чтобы сомелье был", "expected_decision": "search"}
            ]
        },
        {
            "name": "Здоровое питание",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "ищу ресторан здорового питания", "expected_decision": "continue"},
                {"type": "bot", "message": "Веганская кухня или просто органические продукты?"},
                {"type": "user", "message": "органические, много овощей и рыбы", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с кальяном",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу ресторан где можно покурить кальян", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "ближневосточную или индийскую", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан для фотосессии",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "нужно красивое место для фото", "expected_decision": "continue"},
                {"type": "bot", "message": "Какой интерьер ищете?"},
                {"type": "user", "message": "инстаграмное место с видом на море", "expected_decision": "search"}
            ]
        },
        
        # === СЛОЖНЫЕ СЦЕНАРИИ (4-5 вопросов) ===
        {
            "name": "Очень неопределенный клиент",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу поесть", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "не знаю, что-то вкусное", "expected_decision": "continue"},
                {"type": "bot", "message": "А какая компания будет?"},
                {"type": "user", "message": "с друзьями, хотим повеселиться", "expected_decision": "continue"},
                {"type": "bot", "message": "Есть предпочтения по кухне - азиатская, европейская, морепродукты?"},
                {"type": "user", "message": "морепродукты звучит хорошо, и чтобы музыка была", "expected_decision": "search"}
            ]
        },
        {
            "name": "Клиент с аллергией",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "ищу ресторан, но у меня аллергия на морепродукты", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню рассматриваете?"},
                {"type": "user", "message": "что-то безопасное, может европейскую", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая атмосфера нужна?"},
                {"type": "user", "message": "спокойная, ужин с родителями", "expected_decision": "continue"},
                {"type": "bot", "message": "Есть предпочтения по локации?"},
                {"type": "user", "message": "в центре, чтобы легко добраться", "expected_decision": "search"}
            ]
        },
        {
            "name": "Большая группа с разными вкусами",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "нас большая компания, все любят разное", "expected_decision": "continue"},
                {"type": "bot", "message": "Сколько человек и какие основные предпочтения?"},
                {"type": "user", "message": "человек 8, кто-то любит мясо, кто-то рыбу", "expected_decision": "continue"},
                {"type": "bot", "message": "Нужно место с разнообразным меню?"},
                {"type": "user", "message": "да, и чтобы было весело, может с живой музыкой", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая кухня подойдет всем?"},
                {"type": "user", "message": "наверное европейская или интернациональная", "expected_decision": "search"}
            ]
        },
        {
            "name": "Особый случай - предложение руки и сердца",
            "budget": "$$$$",
            "turns": [
                {"type": "user", "message": "очень важный ужин, хочу сделать предложение", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую атмосферу ищете для такого особого момента?"},
                {"type": "user", "message": "максимально романтично, с видом на закат", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитает ваша девушка?"},
                {"type": "user", "message": "она любит итальянскую", "expected_decision": "continue"},
                {"type": "bot", "message": "Нужно уединенное место или терраса?"},
                {"type": "user", "message": "терраса с видом на море, и чтобы можно было музыканта заказать", "expected_decision": "search"}
            ]
        },
        {
            "name": "Клиент-гурман с высокими требованиями",
            "budget": "$$$$",
            "turns": [
                {"type": "user", "message": "ищу ресторан высокой кухни", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "французскую или молекулярную", "expected_decision": "continue"},
                {"type": "bot", "message": "Важен ли шеф-повар и его репутация?"},
                {"type": "user", "message": "да, хочу мишленовский уровень", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая атмосфера нужна?"},
                {"type": "user", "message": "изысканная, для важного делового ужина", "expected_decision": "search"}
            ]
        },
        {
            "name": "Национальная кухня",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу попробовать настоящую тайскую кухню", "expected_decision": "continue"},
                {"type": "bot", "message": "Острую или адаптированную для туристов?"},
                {"type": "user", "message": "настоящую острую, как едят местные", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая атмосфера нужна?"},
                {"type": "user", "message": "аутентичная, может уличная еда", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с музыкой",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу ресторан с живой музыкой", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая музыка и кухня?"},
                {"type": "user", "message": "джаз и европейская кухня", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с террасой",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "хочу поесть на открытом воздухе", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню и какой вид предпочитаете?"},
                {"type": "user", "message": "итальянскую с видом на город", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан для большой семьи",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "семейный ужин, нас много", "expected_decision": "continue"},
                {"type": "bot", "message": "Сколько человек и какие предпочтения?"},
                {"type": "user", "message": "15 человек, нужно разнообразное меню", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая кухня подойдет всем?"},
                {"type": "user", "message": "интернациональная, и чтобы детям было интересно", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с доставкой",
            "budget": "$",
            "turns": [
                {"type": "user", "message": "можно ли заказать еду в отель?", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню хотите заказать?"},
                {"type": "user", "message": "тайскую, том ям и пад тай", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан для свидания вслепую",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "первое свидание, не знаю что она любит", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую атмосферу выберете?"},
                {"type": "user", "message": "не слишком романтично, но приятно", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая кухня универсальная?"},
                {"type": "user", "message": "наверное итальянская, все любят пасту", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан для встречи одноклассников",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "встреча выпускников, нас человек 20", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая атмосфера нужна?"},
                {"type": "user", "message": "чтобы можно было громко общаться и веселиться", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "что-то простое, барбекю или гриль", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан для пожилых родителей",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "ужин с пожилыми родителями", "expected_decision": "continue"},
                {"type": "bot", "message": "Какие особенности нужно учесть?"},
                {"type": "user", "message": "тихое место, не острая еда", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитают?"},
                {"type": "user", "message": "европейскую, привычную еду", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с кондиционером",
            "budget": "$",
            "turns": [
                {"type": "user", "message": "очень жарко, нужно место с хорошим кондиционером", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "что-то легкое, салаты и холодные блюда", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с парковкой",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "нужен ресторан с парковкой", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню и атмосферу ищете?"},
                {"type": "user", "message": "азиатскую, семейный ужин", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с Wi-Fi",
            "budget": "$",
            "turns": [
                {"type": "user", "message": "нужно поработать за ужином", "expected_decision": "continue"},
                {"type": "bot", "message": "Какая атмосфера нужна для работы?"},
                {"type": "user", "message": "тихая, с хорошим Wi-Fi и розетками", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с английским меню",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "не говорю по-тайски, нужно английское меню", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню предпочитаете?"},
                {"type": "user", "message": "интернациональную, понятную", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с дегустационным меню",
            "budget": "$$$$",
            "turns": [
                {"type": "user", "message": "хочу попробовать дегустационное меню", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню интересует?"},
                {"type": "user", "message": "молекулярную или фьюжн", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан для аллергика",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "у меня аллергия на глютен", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню можете есть?"},
                {"type": "user", "message": "тайскую без лапши, рис и овощи", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с детским меню",
            "budget": "$$",
            "turns": [
                {"type": "user", "message": "нужно детское меню", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню для взрослых?"},
                {"type": "user", "message": "европейскую, а детям простые блюда", "expected_decision": "search"}
            ]
        },
        {
            "name": "Ресторан с коктейлями",
            "budget": "$$$",
            "turns": [
                {"type": "user", "message": "хочу ресторан с хорошими коктейлями", "expected_decision": "continue"},
                {"type": "bot", "message": "Какую кухню и атмосферу?"},
                {"type": "user", "message": "азиатскую фьюжн, модное место", "expected_decision": "search"}
            ]
        }
    ]
    
    print("🧠 Тестирование 50 реалистичных диалогов с развитием разговора\n")
    print("📊 Анализ эффективности: за сколько шагов AI доходит до рекомендаций\n")
    
    successful = 0
    total = len(scenarios)
    
    # Статистика по количеству шагов
    steps_stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, "5+": 0}
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*80}")
        print(f"ТЕСТ {i}/50")
        result = await simulate_realistic_dialogue(scenario)
        if result:
            successful += 1
            
            # Подсчитываем количество шагов пользователя до поиска
            user_steps = len([turn for turn in scenario['turns'] if turn['type'] == 'user'])
            if user_steps <= 5:
                steps_stats[user_steps] += 1
            else:
                steps_stats["5+"] += 1
    
    print(f"\n{'='*80}")
    print(f"📊 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*80}")
    
    accuracy = (successful / total) * 100
    print(f"✅ Успешных диалогов: {successful}/{total} ({accuracy:.1f}%)")
    
    print(f"\n📈 РАСПРЕДЕЛЕНИЕ ПО КОЛИЧЕСТВУ ШАГОВ ДО РЕКОМЕНДАЦИИ:")
    print(f"🚀 За 1 шаг:  {steps_stats[1]} диалогов ({steps_stats[1]/total*100:.1f}%)")
    print(f"⚡ За 2 шага: {steps_stats[2]} диалогов ({steps_stats[2]/total*100:.1f}%)")
    print(f"✨ За 3 шага: {steps_stats[3]} диалогов ({steps_stats[3]/total*100:.1f}%)")
    print(f"💫 За 4 шага: {steps_stats[4]} диалогов ({steps_stats[4]/total*100:.1f}%)")
    print(f"⭐ За 5 шагов: {steps_stats[5]} диалогов ({steps_stats[5]/total*100:.1f}%)")
    print(f"🐌 Больше 5:  {steps_stats['5+']} диалогов ({steps_stats['5+']/total*100:.1f}%)")
    
    avg_steps = (1*steps_stats[1] + 2*steps_stats[2] + 3*steps_stats[3] + 4*steps_stats[4] + 5*steps_stats[5] + 6*steps_stats["5+"]) / total
    print(f"\n📊 Среднее количество шагов: {avg_steps:.1f}")
    
    if accuracy >= 90:
        print("🎉 ОТЛИЧНО! AI логика работает превосходно!")
    elif accuracy >= 80:
        print("👍 ХОРОШО! AI понимает большинство диалогов")
    elif accuracy >= 70:
        print("⚠️ УДОВЛЕТВОРИТЕЛЬНО, но есть что улучшать")
    else:
        print("❌ НУЖНЫ СЕРЬЕЗНЫЕ УЛУЧШЕНИЯ в логике")
    
    if avg_steps <= 3:
        print("🚀 СКОРОСТЬ: Отлично! Быстро доходим до рекомендаций")
    elif avg_steps <= 4:
        print("⚡ СКОРОСТЬ: Хорошо! Умеренная скорость диалогов")
    else:
        print("🐌 СКОРОСТЬ: Медленно, нужно ускорить принятие решений")

def test_comprehensive_ai():
    """Запуск комплексного теста AI логики"""
    asyncio.run(run_comprehensive_tests())

if __name__ == "__main__":
    test_comprehensive_ai() 