"""
Модуль для работы с пользователями в базе данных
"""
import logging
from psycopg2.extras import DictCursor
from .connection import get_db_connection

logger = logging.getLogger(__name__)

def save_user_to_db(user_id, username, first_name, last_name, language):
    """Сохраняет пользователя в базу данных. Возвращает True при успехе, False при ошибке"""
    conn = None
    cur = None
    try:
        logger.info(f"Attempting to save user: id={user_id}, username={username}, first_name={first_name}, last_name={last_name}, language={language}")
        
        conn = get_db_connection()
        logger.info("Database connection established")
        
        cur = conn.cursor(cursor_factory=DictCursor)
        logger.info("Cursor created")
        
        # Сохраняем telegram_username отдельно
        telegram_username = username or f"{first_name or ''} {last_name or ''}".strip() or str(user_id)
        logger.info(f"Formed telegram_username: {telegram_username}")
        
        # Проверяем, существует ли пользователь
        check_query = "SELECT client_number FROM users WHERE telegram_user_id = %s"
        logger.info(f"Executing query: {check_query} with params: {user_id}")
        cur.execute(check_query, (user_id,))
        existing_user = cur.fetchone()
        logger.info(f"Existing user check result: {existing_user}")
        
        if existing_user:
            # Обновляем существующего пользователя
            update_query = """
                UPDATE users 
                SET telegram_username = %s, language = %s 
                WHERE telegram_user_id = %s
                RETURNING client_number
            """
            logger.info(f"Executing update query with params: telegram_username={telegram_username}, language={language}, user_id={user_id}")
            cur.execute(update_query, (telegram_username, language, user_id))
            client_number = cur.fetchone()['client_number']
            logger.info(f"Updated existing user with client_number: {client_number}")
        else:
            # Создаем нового пользователя
            insert_query = """
                INSERT INTO users (telegram_user_id, telegram_username, language)
                VALUES (%s, %s, %s)
                RETURNING client_number
            """
            logger.info(f"Executing insert query with params: user_id={user_id}, telegram_username={telegram_username}, language={language}")
            cur.execute(insert_query, (user_id, telegram_username, language))
            client_number = cur.fetchone()['client_number']
            logger.info(f"Created new user with client_number: {client_number}")
        
        conn.commit()
        logger.info(f"Transaction committed successfully")
        return True  # Возвращаем True при успехе
    except Exception as e:
        if conn:
            conn.rollback()
            logger.info("Transaction rolled back due to error")
        logger.error(f"Error saving user to database: {e}")
        logger.error("Full traceback:")
        return False  # Возвращаем False при ошибке
    finally:
        if cur:
            cur.close()
            logger.info("Cursor closed")
        if conn:
            conn.close()

def save_user_preferences(user_id, preferences):
    """Сохраняет предпочтения пользователя в базу данных. Возвращает True при успехе, False при ошибке"""
    if preferences is None:
        logger.warning(f"[DB] Cannot save None preferences for user {user_id}")
        return False
        
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Обновляем предпочтения пользователя
        update_query = """
            UPDATE users 
            SET budget = %s,
                last_search_area = %s,
                last_search_location = %s,
                preferences_updated_at = CURRENT_TIMESTAMP
            WHERE telegram_user_id = %s
        """
        cur.execute(update_query, (
            preferences.get('budget'),
            preferences.get('area'),
            preferences.get('location'),
            user_id
        ))
        
        conn.commit()
        logger.info(f"[DB] Saved preferences for user {user_id}: {preferences}")
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"[DB] Error saving preferences: {e}")
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def get_user_preferences(user_id):
    """Получает предпочтения пользователя из базы данных"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Получаем предпочтения пользователя
        select_query = """
            SELECT budget, last_search_area, last_search_location, language
            FROM users
            WHERE telegram_user_id = %s
        """
        cur.execute(select_query, (user_id,))
        result = cur.fetchone()
        
        if result:
            preferences = {
                'budget': result['budget'],
                'area': result['last_search_area'], 
                'location': result['last_search_location'],
                'language': result['language']
            }
            logger.info(f"[DB] Retrieved preferences for user {user_id}: {preferences}")
            return preferences
        return None
    except Exception as e:
        logger.error(f"[DB] Error getting preferences: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close() 