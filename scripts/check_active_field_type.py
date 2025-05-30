#!/usr/bin/env python3
"""
Скрипт для проверки типа поля active в таблице restaurants
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.bot.database.connection import get_db_connection

def check_active_field_type():
    """Проверяет тип поля active"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'restaurants' AND column_name = 'active';")
        result = cur.fetchone()
        
        if result:
            print(f"Поле active: {result[0]} - тип: {result[1]}")
        else:
            print("Поле active не найдено")
            
        # Проверим также значения в поле
        cur.execute("SELECT DISTINCT active FROM restaurants LIMIT 5;")
        values = cur.fetchall()
        print(f"Значения в поле active: {[v[0] for v in values]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    check_active_field_type() 