#!/usr/bin/env python3
"""
Скрипт для проверки содержимого базы данных BookTable.
Используется для отладки и проверки состояния базы данных.

Функциональность:
- Подключается к базе данных PostgreSQL
- Выводит содержимое таблицы users
- Показывает все поля для каждого пользователя

Использование:
    python3 scripts/check_db.py

Требования:
- PostgreSQL должен быть запущен
- База данных booktable должна существовать
- Пользователь root должен иметь доступ к базе
"""

import psycopg2
from psycopg2.extras import DictCursor

def check_users():
    """
    Проверяет и выводит информацию о пользователях в базе данных.
    """
    try:
        # Подключаемся к базе данных
        conn = psycopg2.connect(
            dbname="booktable",
            user="root",
            host="/var/run/postgresql"
        )
        
        # Создаем курсор с поддержкой именованных колонок
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Получаем всех пользователей
        cur.execute("SELECT * FROM users;")
        users = cur.fetchall()
        
        # Выводим информацию о каждом пользователе
        for user in users:
            print("\nИнформация о пользователе:")
            print(f"Порядковый номер: {user['client_number']}")
            print(f"ID в Telegram: {user['telegram_user_id']}")
            print(f"Имя в Telegram: {user['telegram_username']}")
            print(f"Имя клиента: {user['client_name'] or 'Не указано'}")
            print(f"Телефон: {user['phone'] or 'Не указан'}")
            print(f"Предпочтения по чеку: {user['check_preference'] or 'Не указаны'}")
            print(f"Язык: {user['language']}")
            print("-" * 50)
            
        # Закрываем соединения
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_users() 