"""
Модуль для работы с ресторанами в базе данных
"""
import logging
from psycopg2.extras import DictCursor
from .connection import get_db_connection
from ..constants import AREA_DB_MAPPING

logger = logging.getLogger(__name__)

async def get_restaurants_by_area(area_key, budget_str):
    """Получает рестораны по району и бюджету"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Получаем правильное название района для поиска в базе данных
        db_area_name = AREA_DB_MAPPING.get(area_key, '')
        
        logger.info(f"[RESTAURANTS] Area key: {area_key}, DB area name: {db_area_name}")
        
        # Ищем рестораны с выбранным бюджетом
        query = """
            SELECT r.*
            FROM restaurants r
            WHERE LOWER(r.location) ILIKE %s
            AND r.average_check::text = %s AND r.active = 'TRUE'
            ORDER BY r.name
        """
        params = (f"%{db_area_name.lower()}%", budget_str)

        logger.info(f"[RESTAURANTS] Executing query: {query}")
        logger.info(f"[RESTAURANTS] With params: {params}")
        
        cur.execute(query, params)
        rows = cur.fetchall()
        logger.info(f"[RESTAURANTS] Found {len(rows)} restaurants")
        
        cur.close()
        conn.close()
        
        return [dict(r) for r in rows]
        
    except Exception as e:
        logger.error(f"[RESTAURANTS] Error getting restaurants: {e}")
        return []

async def get_available_budgets_in_area(area_key):
    """Получает доступные бюджеты в районе"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        db_area_name = AREA_DB_MAPPING.get(area_key, '')
        
        cur.execute("""
            SELECT DISTINCT average_check::text as budget
            FROM restaurants 
            WHERE LOWER(location) ILIKE %s
            AND active = 'TRUE'
            ORDER BY average_check::text
        """, (f"%{db_area_name.lower()}%",))
        
        available_budgets = [row['budget'] for row in cur.fetchall()]
        logger.info(f"[RESTAURANTS] Available budgets in area: {available_budgets}")
        
        cur.close()
        conn.close()
        
        return available_budgets
        
    except Exception as e:
        logger.error(f"[RESTAURANTS] Error getting available budgets: {e}")
        return []

async def get_restaurants_by_location_any(budget_str):
    """Получает рестораны по всему острову с заданным бюджетом"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        query = """
            SELECT r.*
            FROM restaurants r
            WHERE r.average_check::text = %s AND r.active = 'TRUE'
            ORDER BY r.name
        """
        params = (budget_str,)

        logger.info(f"[RESTAURANTS] Executing query: {query}")
        logger.info(f"[RESTAURANTS] With params: {params}")
        
        cur.execute(query, params)
        rows = cur.fetchall()
        logger.info(f"[RESTAURANTS] Found {len(rows)} restaurants")
        
        cur.close()
        conn.close()
        
        return [dict(r) for r in rows]
        
    except Exception as e:
        logger.error(f"[RESTAURANTS] Error getting restaurants: {e}")
        return [] 