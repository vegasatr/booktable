"""
Модуль для переводов и определения языка
"""
import logging
from .core import client, ai_generate
from ..config import OPENAI_MODEL
from ..constants import BASE_MESSAGES, PROMPTS

logger = logging.getLogger(__name__)

async def detect_language(text):
    """
    Определяет язык текста через ai_generate (fallback: OpenAI → Yandex).
    Возвращает код языка в формате ISO 639-1.
    """
    try:
        # Проверяем, есть ли промпт для detect_language
        if 'detect_language' not in PROMPTS or 'openai' not in PROMPTS['detect_language']:
            # Если промпта нет, используем простую эвристику
            if any(char in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' for char in text.lower()):
                return 'ru'
            elif any(char in 'àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ' for char in text.lower()):
                return 'fr'
            elif any(char in 'äöüß' for char in text.lower()):
                return 'de'
            else:
                return 'en'
        
        lang = await ai_generate('detect_language', text=text)
        lang = lang.strip().lower()
        # Маппинг для схожих языков
        if lang in ['es', 'ca', 'gl']:
            return 'es'
        elif lang in ['fr', 'oc']:
            return 'fr'
        elif lang in ['ru', 'uk', 'be']:
            return 'ru'
        elif lang in ['zh', 'zh_cn', 'zh_tw']:
            return 'zh'
        elif lang in ['ar', 'fa', 'ur']:
            return 'ar'
        elif lang in ['th', 'lo']:
            return 'th'
        return lang
    except Exception as e:
        logger.error(f"Error detecting language: {e}")
        return 'en'

async def translate_message(message_key, language, **kwargs):
    """
    Переводит базовое сообщение на указанный язык.
    Если язык английский или перевод не удался, возвращает оригинальный текст.
    """
    logger.info(f"[TRANSLATE] message_key={message_key}, language={language}")
    base = BASE_MESSAGES.get(message_key, '')
    if not base:
        logger.error(f"[TRANSLATE] Сообщение не найдено: {message_key}")
        return message_key
        
    if kwargs:
        try:
            base = base.format(**kwargs)
        except KeyError as e:
            logger.error(f"[TRANSLATE] Ошибка форматирования: {e}")
            return base
            
    if language == 'en':
        logger.info("[TRANSLATE] Язык английский, возврат без перевода.")
        return base
    
    try:
        # Системный промпт для переводов
        if message_key.startswith('button_'):
            if language == 'ru':
                # Специальные инструкции для русских кнопок
                system_prompt = f"""Переводчик кнопок на русский. RESERVE→РЕЗЕРВ, QUESTION→ВОПРОС, AREA→РАЙОН. Короткие заглавные буквы. Только перевод."""
            else:
                system_prompt = f"""UI button translator to {language}. Short, concise. Only translation."""
        elif message_key == 'location_send':
            # Специальный промпт для сообщения о запросе геолокации
            system_prompt = f"""Translator to {language}. You are translating a bot message asking USER to share THEIR location. This is NOT a request about bot's location. The bot is asking the user to share their current location. Only translation."""
        elif language == 'ru' and 'Phuket' in base:
            system_prompt = """Переводчик на русский. "in Phuket"→"на Пхукете". Только перевод."""
        else:
            system_prompt = f"""Translator to {language}. Only translation."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": base}
        ]
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=100
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"[TRANSLATE] Успешный перевод: {translated}")
        return translated
    except Exception as e:
        logger.error(f"[TRANSLATE] Ошибка перевода: {e}")
    logger.info("[TRANSLATE] Возврат оригинального текста без перевода.")
    return base

async def translate_text(text: str, target_language: str) -> str:
    """
    Простая функция для перевода текста через AI.
    Использует системный промпт для экономии токенов.
    """
    try:
        system_prompt = f"""You are a translator to {target_language}.
Rules:
- Translate exactly as provided
- Return ONLY the translation, no explanations"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=100
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"[TRANSLATE_TEXT] Translated '{text}' to '{translated}'")
        return translated
    except Exception as e:
        logger.error(f"[TRANSLATE_TEXT] Error translating text: {e}")
        return text 