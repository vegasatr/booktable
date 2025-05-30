"""
Модуль для работы с подключением к ТЕСТОВОЙ базе данных
"""
import logging
import psycopg2
from psycopg2.extras import DictCursor

logger = logging.getLogger(__name__)

def get_db_connection():
    """Устанавливает соединение с PostgreSQL ТЕСТОВОЙ базой"""
    try:
        logger.info("Connecting to TEST database")
        conn = psycopg2.connect(
            dbname="booktable_test",  # ТЕСТОВАЯ БАЗА
            user="root",
            host="/var/run/postgresql"
        )
        logger.info("Successfully connected to TEST database")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"TEST database connection error: {str(e)}")
        logger.error(f"Error code: {e.pgcode if hasattr(e, 'pgcode') else 'N/A'}")
        logger.error(f"Error message: {e.pgerror if hasattr(e, 'pgerror') else 'N/A'}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to TEST database: {str(e)}")
        logger.exception("Full traceback:")
        raise 