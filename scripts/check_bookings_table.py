#!/usr/bin/env python3
"""
Скрипт для проверки и обновления таблицы bookings
Изменяет нумерацию чтобы начинать с 1000
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.bot.database.connection import get_db_connection
from psycopg2.extras import DictCursor

def check_bookings_table():
    """Проверяет структуру таблицы bookings"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=DictCursor)
        
        print("🔍 Проверяем структуру таблицы bookings...")
        
        # Проверяем существование таблицы
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'bookings'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("❌ Таблица bookings не существует!")
            return False
            
        print("✅ Таблица bookings существует")
        
        # Проверяем структуру таблицы
        cur.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'bookings'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        
        print("\n📋 Структура таблицы bookings:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']} (default: {col['column_default']}, nullable: {col['is_nullable']})")
        
        # Проверяем текущие записи
        cur.execute("SELECT COUNT(*) FROM bookings;")
        count = cur.fetchone()[0]
        print(f"\n📊 Текущее количество записей в bookings: {count}")
        
        if count > 0:
            cur.execute("SELECT booking_number FROM bookings ORDER BY booking_number;")
            booking_numbers = [row[0] for row in cur.fetchall()]
            print(f"📋 Существующие номера бронирований: {booking_numbers}")
            
            # Проверяем максимальный номер бронирования
            max_booking = max(booking_numbers)
            print(f"🔢 Максимальный номер бронирования: {max_booking}")
            
            # Проверяем текущее значение sequence (только если возможно)
            try:
                cur.execute("""
                    SELECT last_value FROM bookings_booking_number_seq;
                """)
                last_value = cur.fetchone()[0]
                print(f"🔢 Текущее значение sequence: {last_value}")
            except Exception as e:
                print(f"⚠️ Не удалось получить значение sequence: {e}")
        else:
            print("📋 Таблица пуста")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при проверке таблицы bookings: {e}")
        return False

def update_sequence_to_1000():
    """Устанавливает sequence booking_number начиная с 1000"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        print("\n🔧 Обновляем sequence для начала с 1000...")
        
        # Устанавливаем следующее значение sequence в 1000
        cur.execute("""
            SELECT setval(pg_get_serial_sequence('bookings', 'booking_number'), 1000, false);
        """)
        
        # Проверяем новое значение
        cur.execute("""
            SELECT nextval(pg_get_serial_sequence('bookings', 'booking_number'));
        """)
        next_val = cur.fetchone()[0]
        
        if next_val == 1000:
            print("✅ Sequence успешно обновлен! Следующий booking_number будет: 1000")
            
            # Возвращаем sequence на правильное место (nextval увеличил его)
            cur.execute("""
                SELECT setval(pg_get_serial_sequence('bookings', 'booking_number'), 999, true);
            """)
            
            conn.commit()
            print("✅ Sequence настроен корректно. Следующее бронирование получит номер 1000")
        else:
            print(f"❌ Ошибка: ожидался номер 1000, получен {next_val}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении sequence: {e}")
        if conn:
            conn.rollback()
            cur.close()
            conn.close()
        return False

def test_booking_number_generation():
    """Тестирует генерацию номеров бронирований"""
    try:
        from datetime import date, time
        from src.bot.database.bookings import save_booking_to_db
        import asyncio
        
        print("\n🧪 Тестируем генерацию номера бронирования...")
        
        # Создаем тестовое бронирование
        booking_number = asyncio.run(save_booking_to_db(
            restaurant_name="Test Restaurant",
            client_name="Test User",
            phone="+1234567890",
            date_booking=date.today(),
            time_booking=time(19, 30),
            guests=2,
            restaurant_contact="test@example.com",
            booking_method="telegram",
            preferences="Test booking",
            client_code=12345,
            status="pending"
        ))
        
        if booking_number:
            print(f"✅ Тестовое бронирование создано с номером: {booking_number}")
            
            if booking_number >= 1000:
                print("✅ Нумерация работает корректно (>= 1000)")
            else:
                print(f"❌ Нумерация некорректна: {booking_number} < 1000")
                
            return booking_number
        else:
            print("❌ Ошибка создания тестового бронирования")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return None

def main():
    """Основная функция"""
    print("🚀 Проверка и обновление таблицы bookings")
    print("=" * 50)
    
    # Шаг 1: Проверяем таблицу
    if not check_bookings_table():
        print("❌ Не удалось проверить таблицу bookings")
        return
    
    # Шаг 2: Обновляем sequence
    print("\n" + "=" * 50)
    if not update_sequence_to_1000():
        print("❌ Не удалось обновить sequence")
        return
    
    # Шаг 3: Тестируем генерацию
    print("\n" + "=" * 50)
    test_booking_number = test_booking_number_generation()
    
    if test_booking_number and test_booking_number >= 1000:
        print(f"\n🎉 УСПЕХ! Нумерация обновлена. Следующие бронирования будут начинаться с 1000+")
        print(f"   Тестовое бронирование получило номер: {test_booking_number}")
    else:
        print(f"\n❌ ОШИБКА! Нумерация не работает корректно")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main() 