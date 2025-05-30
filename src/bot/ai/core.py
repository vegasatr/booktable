"""
Основной модуль для работы с OpenAI API
"""
import logging
from openai import OpenAI
from ..config import OPENAI_API_KEY, OPENAI_MODEL
from ..constants import PROMPTS, PHUKET_AREAS

logger = logging.getLogger(__name__)

# Инициализация клиента OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

def get_prompt(task, engine, **kwargs):
    """Получает промпт из конфигурации с подстановкой параметров"""
    template = PROMPTS.get(task, {}).get(engine, "")
    return template.format(**kwargs)

def ping_openai():
    """Быстрая проверка доступности OpenAI"""
    try:
        client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.0,
            max_tokens=1
        )
        return True
    except Exception:
        return False

async def ai_generate(task, text=None, target_language=None, preferences=None, context_log=None, context=None):
    """
    Универсальный слой генерации/диалогов с выбором движка.
    Для генерации ответов, рекомендаций, уточнений и т.д. — только OpenAI.
    task: restaurant_recommendation, greet, clarify, fallback_error, restaurant_qa
    """
    try:
        # Специальная обработка для fallback_error - не отправляем в OpenAI
        if task == 'fallback_error':
            if target_language == 'ru':
                return "Извините, произошла ошибка. Попробуйте ещё раз."
            else:
                return "Sorry, an error occurred. Please try again."
        
        if task == 'restaurant_recommendation':
            prompt = get_prompt('restaurant_recommendation', 'openai', preferences=preferences, target_language=target_language)
        elif task == 'greet':
            prompt = get_prompt('greet', 'openai', target_language=target_language)
        elif task == 'clarify':
            prompt = get_prompt('clarify', 'openai', target_language=target_language)
        elif task == 'restaurant_qa':
            prompt = get_prompt('restaurant_qa', 'openai', text=text)
        else:
            # Для неизвестных задач возвращаем ошибку без обращения к OpenAI
            if target_language == 'ru':
                return "Извините, произошла ошибка. Попробуйте ещё раз."
            else:
                return "Sorry, an error occurred. Please try again."
        
        messages = [{"role": "user", "content": prompt}]
        logger.info(f"[AI] OpenAI prompt: {prompt}")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        if target_language == 'ru':
            return "Извините, произошла ошибка. Попробуйте ещё раз."
        else:
            return "Sorry, an error occurred. Please try again."

async def ask(text, chat_log=None, language='en'):
    """
    Генерирует ответ на сообщение пользователя через ai_generate.
    Возвращает (ответ, обновлённый chat_log).
    """
    try:
        answer = await ai_generate('restaurant_recommendation', text=text, target_language=language, context_log=chat_log)
        # chat_log не обновляем, т.к. ai_generate не ведёт историю
        return answer, chat_log or []
    except Exception as e:
        logger.error(f"Error in ask: {e}")
        return await ai_generate('fallback_error', target_language=language), chat_log or []

async def restaurant_chat(question, restaurant_info, language, context=None):
    """
    Чат о ресторанах с AI-powered контекстным процессором.
    Использует ChatGPT для определения релевантных полей БД.
    """
    try:
        # Короткий системный промпт
        system_prompt = f"Ты консультант по ресторанам Пхукета. Отвечай на языке {language}. Используй данные о ресторане для ответов. Будь дружелюбным и конкретным. Не упоминай AI/базу данных. Отвечай кратко на заданный вопрос."

        # Получаем данные ресторанов из контекста
        restaurants = []
        if context and hasattr(context, 'user_data') and 'filtered_restaurants' in context.user_data:
            restaurants = context.user_data['filtered_restaurants']
            logger.info(f"[RESTAURANT_CHAT] Found {len(restaurants)} restaurants in context")
        
        # Используем AI-powered контекстный процессор для получения только релевантных данных
        if restaurants:
            optimized_restaurant_info = await get_relevant_restaurant_data(question, restaurants, language)
            logger.info(f"[RESTAURANT_CHAT] AI-optimized data length: {len(optimized_restaurant_info)} chars vs original: {len(restaurant_info)} chars")
        else:
            # Fallback к оригинальным данным если нет отфильтрованных ресторанов
            optimized_restaurant_info = restaurant_info

        # Пользовательский запрос - только вопрос и AI-оптимизированные данные о ресторанах
        user_content = f"""Информация о ресторанах:
{optimized_restaurant_info}

Вопрос: {question}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        logger.info(f"[RESTAURANT_CHAT] Sending request to OpenAI with {len(messages)} messages")
        logger.info(f"[RESTAURANT_CHAT] Total content length: {len(user_content)} chars")
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        reply = response.choices[0].message.content.strip()
        logger.info(f"[RESTAURANT_CHAT] Received reply: {reply[:100]}...")
        
        return reply
        
    except Exception as e:
        logger.error(f"[RESTAURANT_CHAT] Error: {e}")
        return "Извините, произошла ошибка при обработке вашего вопроса."

async def get_relevant_restaurant_data(question, restaurants, language):
    """Получает только релевантные данные о ресторанах для вопроса"""
    try:
        # Простая реализация - возвращаем краткую информацию о всех ресторанах
        result = []
        for r in restaurants:
            restaurant_info = f"Restaurant: {r.get('name', '')}"
            if r.get('cuisine'):
                restaurant_info += f", Cuisine: {r['cuisine']}"
            if r.get('average_check'):
                restaurant_info += f", Price: {r['average_check']}"
            if r.get('features'):
                features = r['features']
                if isinstance(features, list):
                    features = ', '.join(features)
                restaurant_info += f", Features: {features}"
            result.append(restaurant_info)
        
        return '\n'.join(result)
        
    except Exception as e:
        logger.error(f"Error getting relevant restaurant data: {e}")
        return "No restaurant data available"

async def detect_area_from_text(text: str, language: str) -> str:
    """Определяет район из текстового ввода пользователя"""
    try:
        text_lower = text.lower()
        
        # Сначала проверяем прямые совпадения
        for area_key, area_name in PHUKET_AREAS.items():
            if area_key.lower() in text_lower or area_name.lower() in text_lower:
                return area_key
        
        # Проверяем альтернативные названия
        area_aliases = {
            'патонг': 'patong',
            'чалонг': 'chalong', 
            'ката': 'kata',
            'карон': 'karon',
            'пхукет таун': 'phuket_town',
            'пхукет-таун': 'phuket_town',
            'камала': 'kamala',
            'равай': 'rawai',
            'най харн': 'nai_harn',
            'банг тао': 'bang_tao'
        }
        
        for alias, area_key in area_aliases.items():
            if alias in text_lower:
                return area_key
        
        logger.info(f"[DETECT_AREA] Could not detect area from text: {text}")
        return None
        
    except Exception as e:
        logger.error(f"[DETECT_AREA] Error: {e}")
        return None

async def general_chat(question, language):
    """
    Общий диалог для отвлеченных тем с вежливым возвратом к ресторанам.
    Оптимизированный системный промпт для человечного, ироничного общения.
    """
    from ..ai.translation import translate_message
    
    # Короткий системный промпт для отвлеченных тем
    system_prompt = f"""Ты дружелюбный консультант по ресторанам Пхукета. Отвечай на языке {language}. 
На отвлеченные темы отвечай с юмором и иронией, но вежливо. Аккуратно намекай на рестораны, не навязывая. 
Будь человечным и остроумным. Не упоминай AI.
ВАЖНО: НЕ рекомендуй конкретные рестораны по названиям. Отвечай максимум 2-3 короткими предложениями."""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        logger.info(f"[GENERAL_CHAT] Off-topic question: {question}")
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.9,  # Больше креативности для юмора и иронии
            max_tokens=150   # Еще короче - максимум 150 токенов
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error in general_chat: {e}")
        return await translate_message('error', language)

async def is_about_restaurants(text: str) -> bool:
    """
    Определяет, касается ли вопрос ресторанов или это отвлеченная тема через ChatGPT
    """
    try:
        system_prompt = """Определи тип вопроса в контексте бота-консультанта по ресторанам:
- "restaurant" = вопросы о еде, ресторанах, меню, ценах, атмосфере заведений, рекомендациях ресторанов
- "general" = отвлеченные темы (кино, погода, работа, общие разговоры)
Отвечай только: "restaurant" или "general"."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.1,  # Низкая температура для стабильности
            max_tokens=10    # Очень короткий ответ
        )
        
        result = response.choices[0].message.content.strip().lower()
        is_restaurant = "restaurant" in result
        
        logger.info(f"[QUESTION_TYPE] '{text}' -> {result} -> {'restaurant' if is_restaurant else 'general'}")
        return is_restaurant
        
    except Exception as e:
        logger.error(f"Error in is_about_restaurants: {e}")
        # Fallback: если ошибка, считаем что это общий вопрос
        return False 