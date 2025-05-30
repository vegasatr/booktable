"""
Константы и конфигурация бота
"""
import json

# Список районов Пхукета
PHUKET_AREAS = {
    'chalong': 'Чалонг',
    'patong': 'Патонг',
    'kata': 'Ката',
    'karon': 'Карон',
    'phuket_town': 'Пхукет-таун',
    'kamala': 'Камала',
    'rawai': 'Равай',
    'nai_harn': 'Най Харн',
    'bang_tao': 'Банг Тао',
    'other': 'Другой'
}

# Сопоставление ключей районов с их названиями в базе данных
AREA_DB_MAPPING = {
    'chalong': 'Chalong',
    'patong': 'Patong',
    'kata': 'Kata',
    'karon': 'Karon',
    'phuket_town': 'Phuket Town',
    'kamala': 'Kamala',
    'rawai': 'Rawai',
    'nai_harn': 'Nai Harn',
    'bang_tao': 'Bang Tao'
}

# Координаты центров районов Пхукета (примерные)
PHUKET_AREAS_COORDS = {
    'chalong': (7.8314, 98.3381),
    'patong': (7.8966, 98.2965),
    'kata': (7.8210, 98.2943),
    'karon': (7.8486, 98.2948),
    'phuket_town': (7.8804, 98.3923),
    'kamala': (7.9506, 98.2807),
    'rawai': (7.7796, 98.3281),
    'nai_harn': (7.7726, 98.3166),
    'bang_tao': (7.9936, 98.2933)
}

# Базовые сообщения на английском
with open('messages/base_messages.txt', 'r', encoding='utf-8') as f:
    BASE_MESSAGES = json.load(f)

# Загружаем промпты
with open('prompts.json', 'r', encoding='utf-8') as f:
    PROMPTS = json.load(f) 