#!/usr/bin/env python3
"""
Универсальный инструмент для работы с базой данных BookTable.
Позволяет выполнять SELECT, UPDATE, INSERT запросы через командную строку.

Примеры использования:

1. Показать все рестораны:
   python3 scripts/db_tool.py --action select --table restaurants --fields "name,booking_contact"

2. Обновить контакт ресторана:
   python3 scripts/db_tool.py --action update --table restaurants --set "booking_contact='@alextex'" --where "name='Nitan'"

3. Показать структуру таблицы:
   python3 scripts/db_tool.py --action describe --table restaurants

4. Показать последние бронирования:
   python3 scripts/db_tool.py --action select --table bookings --fields "*" --where "booking_number > 1" --limit 10

5. Подсчитать записи:
   python3 scripts/db_tool.py --action count --table restaurants --where "active = true"

6. Выполнить произвольный запрос:
   python3 scripts/db_tool.py --action query --sql "SELECT COUNT(*) FROM bookings WHERE date >= '2025-01-01'"

Требования:
- PostgreSQL должен быть запущен
- База данных booktable должна существовать
- Пользователь root должен иметь доступ к базе
"""

import argparse
import psycopg2
from psycopg2.extras import DictCursor
import sys

def connect_db():
    """Подключение к базе данных"""
    try:
        conn = psycopg2.connect(
            dbname="booktable",
            user="root",
            host="/var/run/postgresql"
        )
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        sys.exit(1)

def action_select(args):
    """Выполняет SELECT запрос"""
    conn = connect_db()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    fields = args.fields if args.fields else "*"
    query = f"SELECT {fields} FROM {args.table}"
    
    if args.where:
        query += f" WHERE {args.where}"
    
    if args.order:
        query += f" ORDER BY {args.order}"
        
    if args.limit:
        query += f" LIMIT {args.limit}"
    
    print(f"🔍 Выполняем: {query}")
    
    try:
        cur.execute(query)
        rows = cur.fetchall()
        
        if rows:
            print(f"\n📊 Найдено записей: {len(rows)}")
            print("-" * 80)
            
            for i, row in enumerate(rows, 1):
                print(f"Запись #{i}:")
                for key, value in row.items():
                    print(f"  {key}: {value}")
                print("-" * 40)
        else:
            print("📭 Записи не найдены")
            
    except Exception as e:
        print(f"❌ Ошибка выполнения SELECT: {e}")
    finally:
        cur.close()
        conn.close()

def action_update(args):
    """Выполняет UPDATE запрос"""
    if not args.set:
        print("❌ Для UPDATE нужно указать --set")
        return
        
    conn = connect_db()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    query = f"UPDATE {args.table} SET {args.set}"
    
    if args.where:
        query += f" WHERE {args.where}"
    else:
        print("⚠️  Внимание! UPDATE без WHERE изменит ВСЕ записи!")
        confirm = input("Продолжить? (y/N): ")
        if confirm.lower() != 'y':
            print("Отменено")
            return
    
    print(f"🔄 Выполняем: {query}")
    
    try:
        cur.execute(query)
        affected = cur.rowcount
        conn.commit()
        print(f"✅ Обновлено записей: {affected}")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения UPDATE: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def action_count(args):
    """Подсчитывает количество записей"""
    conn = connect_db()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    query = f"SELECT COUNT(*) as count FROM {args.table}"
    
    if args.where:
        query += f" WHERE {args.where}"
    
    print(f"🔢 Выполняем: {query}")
    
    try:
        cur.execute(query)
        result = cur.fetchone()
        print(f"📊 Количество записей: {result['count']}")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения COUNT: {e}")
    finally:
        cur.close()
        conn.close()

def action_describe(args):
    """Показывает структуру таблицы"""
    conn = connect_db()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
    """
    
    print(f"📋 Структура таблицы {args.table}:")
    
    try:
        cur.execute(query, (args.table,))
        columns = cur.fetchall()
        
        if columns:
            print("-" * 80)
            print(f"{'Поле':<20} {'Тип':<20} {'NULL':<8} {'По умолчанию':<20}")
            print("-" * 80)
            
            for col in columns:
                default = col['column_default'] or ''
                if len(default) > 18:
                    default = default[:15] + '...'
                    
                print(f"{col['column_name']:<20} {col['data_type']:<20} {col['is_nullable']:<8} {default:<20}")
        else:
            print(f"❌ Таблица '{args.table}' не найдена")
            
    except Exception as e:
        print(f"❌ Ошибка получения структуры: {e}")
    finally:
        cur.close()
        conn.close()

def action_query(args):
    """Выполняет произвольный SQL запрос"""
    if not args.sql:
        print("❌ Для --action query нужно указать --sql")
        return
        
    conn = connect_db()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    print(f"⚡ Выполняем: {args.sql}")
    
    try:
        cur.execute(args.sql)
        
        # Проверяем тип запроса
        if args.sql.strip().upper().startswith('SELECT'):
            rows = cur.fetchall()
            if rows:
                print(f"\n📊 Результат ({len(rows)} записей):")
                print("-" * 80)
                
                for i, row in enumerate(rows, 1):
                    print(f"Запись #{i}:")
                    for key, value in row.items():
                        print(f"  {key}: {value}")
                    print("-" * 40)
            else:
                print("📭 Записи не найдены")
        else:
            # Для UPDATE/INSERT/DELETE
            affected = cur.rowcount
            conn.commit()
            print(f"✅ Затронуто записей: {affected}")
            
    except Exception as e:
        print(f"❌ Ошибка выполнения запроса: {e}")
        if 'UPDATE' in args.sql.upper() or 'INSERT' in args.sql.upper() or 'DELETE' in args.sql.upper():
            conn.rollback()
    finally:
        cur.close()
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Универсальный инструмент для работы с БД BookTable')
    
    parser.add_argument('--action', required=True, 
                       choices=['select', 'update', 'count', 'describe', 'query'],
                       help='Действие: select/update/count/describe/query')
    
    parser.add_argument('--table', help='Имя таблицы')
    parser.add_argument('--fields', help='Поля для SELECT (через запятую)')
    parser.add_argument('--where', help='Условие WHERE')
    parser.add_argument('--set', help='Значения для UPDATE (поле=значение)')
    parser.add_argument('--order', help='Сортировка ORDER BY')
    parser.add_argument('--limit', type=int, help='Ограничение LIMIT')
    parser.add_argument('--sql', help='Произвольный SQL запрос')
    
    args = parser.parse_args()
    
    # Проверяем обязательные параметры
    if args.action in ['select', 'update', 'count', 'describe'] and not args.table:
        print("❌ Для этого действия нужно указать --table")
        sys.exit(1)
    
    if args.action == 'query' and not args.sql:
        print("❌ Для --action query нужно указать --sql")
        sys.exit(1)
    
    # Выполняем действие
    if args.action == 'select':
        action_select(args)
    elif args.action == 'update':
        action_update(args)
    elif args.action == 'count':
        action_count(args)
    elif args.action == 'describe':
        action_describe(args)
    elif args.action == 'query':
        action_query(args)

if __name__ == "__main__":
    main() 