#!/usr/bin/env python3
"""
Модуль для интеллектуальной обработки контекста запросов пользователей.
Определяет, какие поля базы данных нужно передать в ChatGPT на основе вопроса.
"""

import re
import logging
from typing import List, Dict, Set, Any
from dataclasses import dataclass
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

# Настройка OpenAI
openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@dataclass
class FieldMapping:
    """Маппинг концепций на поля базы данных"""
    concepts: List[str]  # Концепции/темы
    fields: List[str]    # Соответствующие поля БД
    priority: int        # 1-высокий, 2-средний, 3-низкий

class AIContextProcessor:
    """
    AI-powered контекстный процессор для определения релевантных полей БД
    """
    
    def __init__(self):
        # Базовые поля, которые всегда включаются
        self.base_fields = ['name', 'cuisine', 'average_check', 'location']
        
        # Маппинг концепций на поля БД
        self.concept_mappings = self._initialize_concept_mappings()
    
    def _initialize_concept_mappings(self) -> List[FieldMapping]:
        """Инициализирует маппинги концепций на поля БД"""
        return [
            # Еда и блюда
            FieldMapping(
                concepts=['еда', 'блюда', 'меню', 'кухня', 'готовят', 'подают', 'специальности', 'рекомендации', 'вкусно'],
                fields=['key_dishes', 'meal_types', 'menu_options', 'dish_of_the_day', 'tasting_menu', 'spicy_dishes', 'customizable_dishes'],
                priority=1
            ),
            
            # Напитки
            FieldMapping(
                concepts=['напитки', 'алкоголь', 'вино', 'коктейли', 'пиво', 'безалкогольные', 'кофе', 'чай', 'сомелье'],
                fields=['wine_list', 'cocktails', 'non_alcoholic_drinks', 'coffee_tea_options', 'sommelier_available', 'drink_specials', 'corkage_fee'],
                priority=1
            ),
            
            # Атмосфера и обстановка
            FieldMapping(
                concepts=['атмосфера', 'обстановка', 'интерьер', 'музыка', 'шум', 'романтично', 'уютно', 'стиль', 'дизайн'],
                fields=['atmosphere', 'noise_level', 'romantic', 'instagrammable', 'unique_features', 'story_or_concept'],
                priority=2
            ),
            
            # Семья и дети
            FieldMapping(
                concepts=['дети', 'семья', 'детское меню', 'стульчики', 'развлечения', 'анимация', 'семейный'],
                fields=['child_friendly', 'kids_menu', 'kids_area', 'high_chairs', 'animation_family_entertainment'],
                priority=1
            ),
            
            # Бронирование и контакты
            FieldMapping(
                concepts=['бронирование', 'резерв', 'заказ столика', 'телефон', 'контакты', 'сайт', 'инстаграм', 'адрес'],
                fields=['booking_method', 'booking_contact', 'reservation_required', 'phone', 'website', 'instagram', 'address'],
                priority=2
            ),
            
            # Время работы
            FieldMapping(
                concepts=['время работы', 'часы', 'открыт', 'закрыт', 'график', 'выходные', 'расписание'],
                fields=['working_hours', 'active'],
                priority=2
            ),
            
            # Оплата и цены
            FieldMapping(
                concepts=['оплата', 'карты', 'наличные', 'цены', 'стоимость', 'дорого', 'дешево', 'скидки', 'акции'],
                fields=['payment_methods', 'discount', 'average_check'],
                priority=2
            ),
            
            # Услуги и сервис
            FieldMapping(
                concepts=['доставка', 'вынос', 'кейтеринг', 'wifi', 'интернет', 'языки', 'QR меню', 'приложение', 'чат'],
                fields=['takeaway_available', 'delivery_options', 'catering_available', 'wi_fi', 'languages_spoken', 'menu_languages', 'qr_menu', 'mobile_app', 'online_chat_available'],
                priority=2
            ),
            
            # Диетические потребности
            FieldMapping(
                concepts=['аллергия', 'диета', 'веган', 'вегетариан', 'безглютен', 'халяль', 'кошер', 'органик', 'эко'],
                fields=['allergen_info', 'dietary_options', 'organic_local_ingredients', 'sustainability_policy'],
                priority=1
            ),
            
            # Мероприятия и группы
            FieldMapping(
                concepts=['группы', 'компании', 'мероприятия', 'банкеты', 'свадьбы', 'корпоративы', 'частные залы'],
                fields=['group_friendly', 'event_support', 'private_dining', 'business_friendly'],
                priority=2
            ),
            
            # Знаменитости и популярность
            FieldMapping(
                concepts=['знаменитости', 'звезды', 'известные люди', 'VIP', 'селебрити', 'популярные гости', 'известные посетители'],
                fields=['celebrity_visits', 'notable_mentions', 'press_features', 'popular_with'],
                priority=2
            ),
            
            # Рейтинги и отзывы
            FieldMapping(
                concepts=['рейтинг', 'отзывы', 'оценки', 'Google', 'TripAdvisor', 'Мишлен', 'награды', 'признание'],
                fields=['google_rating', 'tripadvisor_rating', 'michelin', 'notable_mentions', 'customer_quotes'],
                priority=2
            ),
            
            # Локация и окрестности
            FieldMapping(
                concepts=['где находится', 'район', 'близко', 'рядом', 'достопримечательности', 'пляж', 'центр', 'карта'],
                fields=['location', 'address', 'map_link', 'nearby_landmarks'],
                priority=2
            ),
            
            # Особенности и уникальность
            FieldMapping(
                concepts=['особенности', 'уникальность', 'фишки', 'концепция', 'история', 'шеф-повар', 'интерьер'],
                fields=['unique_features', 'story_or_concept', 'chef_interaction'],
                priority=2
            ),
            
            # Удобства и доступность
            FieldMapping(
                concepts=['терраса', 'вид', 'кондиционер', 'курение', 'животные', 'инвалиды', 'доступность'],
                fields=['outdoor_seating', 'view_sea_garden_city', 'air_conditioning', 'smoking_area', 'pet_friendly', 'accessibility'],
                priority=2
            )
        ]
    
    async def get_relevant_concepts(self, question: str, language: str = 'ru') -> List[str]:
        """
        Использует AI для определения концепций, необходимых для ответа на вопрос
        
        Args:
            question: Вопрос пользователя
            language: Язык вопроса
            
        Returns:
            Список концепций/тем для поиска в БД
        """
        try:
            system_prompt = f"""Ты эксперт по ресторанам. Проанализируй вопрос пользователя и определи, какие аспекты/характеристики ресторана нужны для квалифицированного ответа.

Верни список из 3-7 ключевых концепций/тем на языке {language}, которые помогут найти нужную информацию в базе данных ресторана.

Примеры:
- "Есть ли детское меню?" → ["дети", "семья", "детское меню", "стульчики"]
- "Какое вино?" → ["напитки", "алкоголь", "вино", "винная карта"]
- "Знаменитости посещают?" → ["знаменитости", "VIP гости", "популярность", "известные посетители"]

Отвечай только списком концепций через запятую, без объяснений."""

            response = client.chat.completions.create(
                model=openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            concepts_text = response.choices[0].message.content.strip()
            concepts = [concept.strip() for concept in concepts_text.split(',')]
            
            logger.info(f"[AI-CONTEXT] Question: '{question}' → Concepts: {concepts}")
            return concepts
            
        except Exception as e:
            logger.error(f"[AI-CONTEXT] Error getting concepts: {e}")
            # Fallback: возвращаем базовые концепции
            return ["общая информация", "основные характеристики"]
    
    def find_relevant_fields(self, concepts: List[str]) -> Set[str]:
        """
        Находит поля БД, соответствующие концепциям от AI
        
        Args:
            concepts: Список концепций от AI
            
        Returns:
            Set релевантных полей БД
        """
        relevant_fields = set(self.base_fields)  # Начинаем с базовых полей
        
        # Нормализуем концепции для поиска
        normalized_concepts = [concept.lower().strip() for concept in concepts]
        
        field_scores = {}
        
        for mapping in self.concept_mappings:
            score = 0
            matched_concepts = []
            
            # Ищем пересечения между концепциями AI и нашими маппингами
            for ai_concept in normalized_concepts:
                for mapping_concept in mapping.concepts:
                    # Проверяем вхождение (частичное совпадение)
                    if (ai_concept in mapping_concept.lower() or 
                        mapping_concept.lower() in ai_concept or
                        self._semantic_similarity(ai_concept, mapping_concept.lower())):
                        score += 1
                        matched_concepts.append(f"{ai_concept}→{mapping_concept}")
                        break
            
            if score > 0:
                # Учитываем приоритет маппинга
                weighted_score = score * (4 - mapping.priority)
                
                for field in mapping.fields:
                    if field not in field_scores:
                        field_scores[field] = 0
                    field_scores[field] += weighted_score
                
                logger.info(f"[AI-CONTEXT] Matched concepts for {mapping.fields}: {matched_concepts} (score: {weighted_score})")
        
        # Добавляем поля с достаточным скором
        threshold = 1
        for field, score in field_scores.items():
            if score >= threshold:
                relevant_fields.add(field)
                logger.info(f"[AI-CONTEXT] Added field '{field}' with score {score}")
        
        logger.info(f"[AI-CONTEXT] Final relevant fields: {relevant_fields}")
        return relevant_fields
    
    def _semantic_similarity(self, concept1: str, concept2: str) -> bool:
        """
        Простая проверка семантической близости концепций
        """
        # Словарь синонимов для улучшения поиска
        synonyms = {
            'знаменитости': ['звезды', 'селебрити', 'известные', 'vip', 'популярные'],
            'дети': ['семья', 'детский', 'ребенок', 'малыши'],
            'напитки': ['алкоголь', 'вино', 'коктейли', 'пиво'],
            'еда': ['блюда', 'меню', 'кухня', 'готовят'],
            'время': ['часы', 'работа', 'график', 'расписание'],
            'цены': ['стоимость', 'оплата', 'дорого', 'дешево']
        }
        
        for key, values in synonyms.items():
            if (concept1 in key or key in concept1) and (concept2 in values or any(v in concept2 for v in values)):
                return True
            if (concept2 in key or key in concept2) and (concept1 in values or any(v in concept1 for v in values)):
                return True
        
        return False
    
    def filter_restaurant_data(self, restaurants: List[Dict[str, Any]], relevant_fields: Set[str]) -> List[Dict[str, Any]]:
        """
        Фильтрует данные ресторанов, оставляя только релевантные поля
        """
        filtered_restaurants = []
        
        for restaurant in restaurants:
            filtered_restaurant = {}
            
            for field in relevant_fields:
                if field in restaurant and restaurant[field]:
                    value = restaurant[field]
                    if value and str(value).strip() and str(value).strip().lower() not in ['none', 'null', '']:
                        filtered_restaurant[field] = value
            
            if filtered_restaurant:
                filtered_restaurants.append(filtered_restaurant)
        
        logger.info(f"[AI-CONTEXT] Filtered {len(restaurants)} restaurants to {len(filtered_restaurants)} with relevant data")
        return filtered_restaurants
    
    def format_for_chatgpt(self, filtered_restaurants: List[Dict[str, Any]]) -> str:
        """
        Форматирует отфильтрованные данные для передачи в ChatGPT
        """
        if not filtered_restaurants:
            return "Нет данных о ресторанах."
        
        formatted_data = []
        
        for restaurant in filtered_restaurants:
            restaurant_info = []
            
            # Название всегда первое
            if 'name' in restaurant:
                restaurant_info.append(f"Restaurant: {restaurant['name']}")
            
            # Остальные поля в алфавитном порядке
            for field, value in sorted(restaurant.items()):
                if field != 'name':
                    field_name = field.replace('_', ' ').title()
                    restaurant_info.append(f"{field_name}: {value}")
            
            formatted_data.append('\n'.join(restaurant_info))
        
        result = '\n\n'.join(formatted_data)
        logger.info(f"[AI-CONTEXT] Formatted data length: {len(result)} characters")
        return result

# Глобальный экземпляр процессора
ai_context_processor = AIContextProcessor()

async def get_relevant_restaurant_data(question: str, restaurants: List[Dict[str, Any]], language: str = 'ru') -> str:
    """
    Главная функция для получения релевантных данных ресторанов на основе вопроса
    
    Args:
        question: Вопрос пользователя
        restaurants: Список ресторанов из БД
        language: Язык вопроса
        
    Returns:
        Отформатированная строка с релевантными данными для ChatGPT
    """
    try:
        # Шаг 1: AI определяет концепции
        concepts = await ai_context_processor.get_relevant_concepts(question, language)
        
        # Шаг 2: Находим соответствующие поля БД
        relevant_fields = ai_context_processor.find_relevant_fields(concepts)
        
        # Шаг 3: Фильтруем данные ресторанов
        filtered_restaurants = ai_context_processor.filter_restaurant_data(restaurants, relevant_fields)
        
        # Шаг 4: Форматируем для ChatGPT
        return ai_context_processor.format_for_chatgpt(filtered_restaurants)
        
    except Exception as e:
        logger.error(f"[AI-CONTEXT] Error in get_relevant_restaurant_data: {e}")
        # Fallback: возвращаем базовые данные
        basic_fields = {'name', 'cuisine', 'average_check', 'location'}
        filtered_restaurants = ai_context_processor.filter_restaurant_data(restaurants, basic_fields)
        return ai_context_processor.format_for_chatgpt(filtered_restaurants) 