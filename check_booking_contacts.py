#!/usr/bin/env python3
import psycopg2
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

try:
    # Пробуем подключиться к тестовой БД
    conn = psycopg2.connect('postgresql://postgres@localhost/booktable_test')
    db_name = "booktable_test"
    
except:
    try:
        # Если тестовой нет, к основной
        database_url = os.getenv('DATABASE_URL', 'postgresql://postgres@localhost/booktable')
        conn = psycopg2.connect(database_url)
        db_name = "booktable"
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        exit(1)

try:
    cur = conn.cursor()
    print(f"=== Проверка booking_contact в {db_name} ===")
    
    # Проверяем все рестораны
    cur.execute('SELECT name, booking_contact FROM restaurants LIMIT 5;')
    results = cur.fetchall()
    
    print("\nВсе рестораны:")
    for row in results:
        contact = row[1] if row[1] else "НЕТ КОНТАКТА"
        print(f"  {row[0]}: {contact}")
    
    # Проверяем только с контактами
    cur.execute("SELECT name, booking_contact FROM restaurants WHERE booking_contact IS NOT NULL AND booking_contact != '';")
    contacts = cur.fetchall()
    
    print(f"\nРестораны с контактами ({len(contacts)}):")
    for row in contacts:
        print(f"  {row[0]}: {row[1]}")
    
    # Проверяем последние бронирования
    cur.execute("SELECT booking_number, restaurant, restaurant_contact, status FROM bookings ORDER BY booking_number DESC LIMIT 3;")
    bookings = cur.fetchall()
    
    print(f"\nПоследние бронирования ({len(bookings)}):")
    for row in bookings:
        print(f"  Бронь #{row[0]}: {row[1]} -> {row[2] or 'НЕТ КОНТАКТА'} (статус: {row[3]})")
    
    conn.close()
    print(f"\n✅ Проверка завершена для БД: {db_name}")

except Exception as e:
    print(f"Ошибка выполнения запроса: {e}") 