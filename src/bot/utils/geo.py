"""
Модуль для работы с геолокацией и определением районов
"""
import logging
import math
from ..constants import PHUKET_AREAS_COORDS

logger = logging.getLogger(__name__)

def get_nearest_area(lat, lon):
    """Определяет ближайший район Пхукета по координатам"""
    try:
        min_distance = float('inf')
        nearest_area = None
        
        for area_key, (area_lat, area_lon) in PHUKET_AREAS_COORDS.items():
            # Вычисляем расстояние по формуле гаверсинуса
            distance = calculate_distance(lat, lon, area_lat, area_lon)
            
            if distance < min_distance:
                min_distance = distance
                nearest_area = area_key
        
        logger.info(f"[GEO] Nearest area to ({lat}, {lon}): {nearest_area} (distance: {min_distance:.2f} km)")
        return nearest_area
        
    except Exception as e:
        logger.error(f"[GEO] Error determining nearest area: {e}")
        return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """Вычисляет расстояние между двумя точками по формуле гаверсинуса"""
    # Радиус Земли в километрах
    R = 6371.0
    
    # Конвертируем градусы в радианы
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Разности координат
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Формула гаверсинуса
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Расстояние
    distance = R * c
    
    return distance 