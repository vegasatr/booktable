#!/bin/bash

# Скрипт создания тестовой базы данных BookTable
# Создает точную копию структуры основной БД с тестовыми данными

echo "🗄️ Создание тестовой базы данных BookTable..."

# Проверяем что мы root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт от root"
    exit 1
fi

# Переходим в папку postgres
sudo -u postgres bash << 'EOF'

echo "1️⃣ Создаем тестовую базу данных..."
createdb booktable_test 2>/dev/null || {
    echo "⚠️ База booktable_test уже существует, пересоздаем..."
    dropdb booktable_test
    createdb booktable_test
}

echo "2️⃣ Применяем структуру из init_db.sql..."
psql -d booktable_test -f /root/booktable_bot/init_db.sql

echo "3️⃣ Добавляем тестовые данные..."
psql -d booktable_test << 'EOSQL'

-- Добавляем тестовых пользователей
INSERT INTO users (telegram_user_id, client_name, phone, check_preference, language) VALUES
(12345, 'Test User', '+7-999-123-45-67', '$$', 'en'),
(54321, 'Тест Пользователь', '+7-999-765-43-21', '$$$', 'ru'),
(98765, 'テストユーザー', '+81-90-1234-5678', '$$$$', 'ja');

-- Добавляем тестовые рестораны
INSERT INTO restaurants (
    name, cuisine, location, atmosphere, average_check, features, working_hours, 
    booking_method, booking_contact, active, coordinates, address, phone
) VALUES 
(
    'Test Italian Restaurant',
    'Italian',
    'Patong Beach',
    'Romantic, cozy atmosphere with candlelit tables',
    '$$$',
    ARRAY['Romantic', 'Wine selection', 'Outdoor seating'],
    '{"open": "18:00", "close": "23:00"}',
    'telegram',
    '@test_italian',
    'true',
    POINT(98.2980, 7.8804),
    '123 Beach Road, Patong',
    '+66-76-123-456'
),
(
    'Test Thai Restaurant',
    'Thai',
    'Kata Beach',
    'Authentic Thai experience with traditional decor',
    '$$',
    ARRAY['Authentic', 'Spicy food', 'Local favorite'],
    '{"open": "17:00", "close": "22:00"}',
    'telegram',
    '@test_thai',
    'true',
    POINT(98.3061, 7.8167),
    '456 Kata Road, Kata',
    '+66-76-654-321'
),
(
    'Test French Bistro',
    'French',
    'Phuket Town',
    'Elegant French bistro with intimate setting',
    '$$$$',
    ARRAY['Fine dining', 'Wine pairing', 'Chef recommendations'],
    '{"open": "19:00", "close": "24:00"}',
    'telegram',
    '@test_french',
    'true',
    POINT(98.3923, 7.8906),
    '789 Old Town Street, Phuket Town',
    '+66-76-987-654'
),
(
    'Blue Elephant Test',
    'Thai',
    'Surin Beach',
    'Upscale Thai restaurant with royal cuisine',
    '$$$',
    ARRAY['Royal Thai', 'Elegant', 'Special occasion'],
    '{"open": "18:30", "close": "23:30"}',
    'telegram',
    '@blue_elephant_test',
    'true',
    POINT(98.2761, 7.9658),
    '321 Surin Beach Road',
    '+66-76-456-789'
),
(
    'Red Dragon Test',
    'Chinese',
    'Kamala Beach',
    'Traditional Chinese restaurant with authentic flavors',
    '$$',
    ARRAY['Authentic', 'Family friendly', 'Large portions'],
    '{"open": "17:30", "close": "22:30"}',
    'telegram',
    '@red_dragon_test',
    'true',
    POINT(98.2845, 7.9562),
    '654 Kamala Road',
    '+66-76-789-012'
);

-- Добавляем тестовые бронирования
INSERT INTO bookings (
    date, time, client_name, phone, guests, restaurant, booking_method,
    restaurant_contact, preferences, client_code, status, comment
) VALUES 
(
    CURRENT_DATE + INTERVAL '1 day',
    '19:30',
    'Test User',
    '+7-999-123-45-67',
    2,
    'Test Italian Restaurant',
    'telegram',
    '@test_italian',
    'Window table please',
    '12345',
    'pending',
    'Created by test script'
),
(
    CURRENT_DATE + INTERVAL '2 days',
    '20:00',
    'Тест Пользователь',
    '+7-999-765-43-21',
    4,
    'Blue Elephant Test',
    'telegram',
    '@blue_elephant_test',
    'Столик на веранде',
    '54321',
    'confirmed',
    'Test booking in Russian'
),
(
    CURRENT_DATE,
    '18:00',
    'テストユーザー',
    '+81-90-1234-5678',
    3,
    'Test Thai Restaurant',
    'telegram',
    '@test_thai',
    'Mild spicy level please',
    '98765',
    'pending',
    'Test booking in Japanese'
);

EOSQL

echo "✅ Тестовая база данных создана!"
echo "📊 Статистика:"
echo "   - Пользователей: $(psql -d booktable_test -t -c 'SELECT COUNT(*) FROM users;' | xargs)"
echo "   - Ресторанов: $(psql -d booktable_test -t -c 'SELECT COUNT(*) FROM restaurants;' | xargs)"
echo "   - Бронирований: $(psql -d booktable_test -t -c 'SELECT COUNT(*) FROM bookings;' | xargs)"

EOF

echo ""
echo "🎉 Тестовая база данных готова!"
echo "📝 Для использования в тестах обновите connection.py:"
echo "   dbname=\"booktable_test\""
echo ""
echo "🗑️ Для удаления: sudo -u postgres dropdb booktable_test" 