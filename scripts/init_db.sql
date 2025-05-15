-- Скрипт инициализации базы данных BookTable
-- Версия: 1.0.0
-- Дата: 2024-03-15
-- Описание: Создает структуру базы данных для бота BookTable
--
-- Структура базы:
-- 1. Таблица users - информация о пользователях
-- 2. Таблица bookings - информация о бронированиях
-- 3. Таблица restaurants - информация о ресторанах
--
-- Использование:
--     psql -h /var/run/postgresql -U root -d booktable -f scripts/init_db.sql
--
-- Требования:
-- - PostgreSQL должен быть запущен
-- - База данных booktable должна существовать
-- - Пользователь root должен иметь права на создание таблиц

-- Создание таблицы Users
-- Хранит информацию о пользователях бота
CREATE TABLE users (
    client_number SERIAL PRIMARY KEY,           -- Уникальный номер клиента
    telegram_user_id BIGINT UNIQUE NOT NULL,    -- ID пользователя в Telegram
    telegram_username VARCHAR(255),             -- Имя пользователя в Telegram
    client_name VARCHAR(255),                   -- Реальное имя клиента (заполняется при первом заказе)
    phone VARCHAR(50),                          -- Телефон клиента
    check_preference VARCHAR(10),               -- Предпочтения по чеку
    language VARCHAR(10) NOT NULL               -- Язык интерфейса
);

-- Создание таблицы Bookings
-- Хранит информацию о бронированиях столиков
CREATE TABLE bookings (
    booking_number SERIAL PRIMARY KEY,          -- Уникальный номер бронирования
    date DATE NOT NULL,                         -- Дата бронирования
    time TIME NOT NULL,                         -- Время бронирования
    client_name VARCHAR(255) NOT NULL,          -- Имя клиента
    phone VARCHAR(50) NOT NULL,                 -- Телефон клиента
    guests INTEGER NOT NULL,                    -- Количество гостей
    restaurant VARCHAR(255) NOT NULL,           -- Название ресторана
    booking_method VARCHAR(50),                 -- Способ бронирования
    restaurant_contact VARCHAR(255),            -- Контакты ресторана
    preferences TEXT,                           -- Предпочтения клиента
    client_code VARCHAR(50),                    -- Код клиента
    discount DECIMAL(5,2),                      -- Скидка
    status VARCHAR(50) NOT NULL,                -- Статус бронирования
    comment TEXT                                -- Комментарий
);

-- Создание таблицы Restaurants
-- Хранит подробную информацию о ресторанах
CREATE TABLE restaurants (
    id SERIAL PRIMARY KEY,                      -- Уникальный идентификатор
    name VARCHAR(255) NOT NULL,                 -- Название ресторана
    cuisine VARCHAR(255),                       -- Тип кухни
    location VARCHAR(255),                      -- Расположение
    atmosphere TEXT,                            -- Атмосфера
    average_check DECIMAL(10,2),                -- Средний чек
    features TEXT[],                            -- Особенности
    working_hours JSONB,                        -- Часы работы
    booking_method VARCHAR(50),                 -- Способ бронирования
    booking_contact VARCHAR(255),               -- Контакты для бронирования
    active BOOLEAN DEFAULT true,                -- Активен ли ресторан
    discount DECIMAL(5,2),                      -- Скидка
    key_dishes TEXT[],                          -- Ключевые блюда
    michelin BOOLEAN,                           -- Есть ли звезда Мишлен
    map_link TEXT,                              -- Ссылка на карту
    meal_types TEXT[],                          -- Типы блюд
    service_options TEXT[],                     -- Опции обслуживания
    dietary_options TEXT[],                     -- Диетические опции
    occasions TEXT[],                           -- Поводы для посещения
    drinks_entertainment TEXT[],                -- Напитки и развлечения
    accessibility TEXT[],                       -- Доступность
    address TEXT,                               -- Адрес
    phone VARCHAR(50),                          -- Телефон
    website TEXT,                               -- Веб-сайт
    instagram TEXT,                             -- Instagram
    tripadvisor_link TEXT,                      -- Ссылка на TripAdvisor
    reservation_required BOOLEAN,               -- Требуется ли бронирование
    payment_methods TEXT[],                     -- Способы оплаты
    wifi BOOLEAN,                               -- Есть ли Wi-Fi
    languages_spoken TEXT[],                    -- Языки персонала
    menu_languages TEXT[],                      -- Языки меню
    menu_options TEXT[],                        -- Опции меню
    spicy_dishes BOOLEAN,                       -- Есть ли острые блюда
    kids_menu BOOLEAN,                          -- Есть ли детское меню
    portion_size VARCHAR(50),                   -- Размер порций
    customizable_dishes BOOLEAN,                -- Можно ли изменять блюда
    dish_of_the_day BOOLEAN,                    -- Есть ли блюдо дня
    organic_local_ingredients BOOLEAN,          -- Используются ли местные органические продукты
    tasting_menu BOOLEAN,                       -- Есть ли дегустационное меню
    takeaway_available BOOLEAN,                 -- Доступен ли навынос
    delivery_options TEXT[],                    -- Опции доставки
    catering_available BOOLEAN,                 -- Доступен ли кейтеринг
    allergen_info TEXT,                         -- Информация об аллергенах
    product_source_info TEXT,                   -- Информация об источниках продуктов
    sustainability_policy TEXT,                 -- Политика устойчивого развития
    drink_specials TEXT[],                      -- Специальные напитки
    corkage_fee DECIMAL(10,2),                  -- Плата за принесенное вино
    wine_list TEXT[],                           -- Список вин
    cocktails TEXT[],                           -- Коктейли
    non_alcoholic_drinks TEXT[],                -- Безалкогольные напитки
    coffee_tea_options TEXT[],                  -- Опции кофе и чая
    sommelier_available BOOLEAN,                -- Есть ли сомелье
    noise_level VARCHAR(50),                    -- Уровень шума
    outdoor_seating BOOLEAN,                    -- Есть ли места на улице
    view TEXT[],                                -- Вид
    air_conditioning BOOLEAN,                   -- Есть ли кондиционер
    smoking_area BOOLEAN,                       -- Есть ли зона для курения
    pet_friendly BOOLEAN,                       -- Можно ли с питомцами
    child_friendly BOOLEAN,                     -- Подходит ли для детей
    kids_area BOOLEAN,                          -- Есть ли детская зона
    high_chairs BOOLEAN,                        -- Есть ли детские стульчики
    animation_family_entertainment BOOLEAN,     -- Есть ли анимация и развлечения для семьи
    dress_code VARCHAR(255),                    -- Дресс-код
    power_sockets BOOLEAN,                      -- Есть ли розетки
    qr_menu BOOLEAN,                            -- Есть ли QR-меню
    mobile_app BOOLEAN,                         -- Есть ли мобильное приложение
    online_chat_available BOOLEAN,              -- Доступен ли онлайн-чат
    private_dining BOOLEAN,                     -- Есть ли приватная зона
    group_friendly BOOLEAN,                     -- Подходит ли для групп
    event_support BOOLEAN,                      -- Поддерживает ли мероприятия
    gift_cards BOOLEAN,                         -- Есть ли подарочные карты
    holiday_specials BOOLEAN,                   -- Есть ли специальные предложения на праздники
    romantic BOOLEAN,                           -- Подходит ли для романтических встреч
    instagrammable BOOLEAN,                     -- Подходит ли для Instagram
    chef_interaction BOOLEAN,                   -- Есть ли взаимодействие с шефом
    unique_features TEXT[],                     -- Уникальные особенности
    story_or_concept TEXT,                      -- История или концепция
    nearby_landmarks TEXT[],                    -- Ближайшие достопримечательности
    popular_with TEXT[],                        -- Популярен среди
    solo_friendly BOOLEAN,                      -- Подходит ли для одиночных посетителей
    senior_friendly BOOLEAN,                    -- Подходит ли для пожилых
    tourist_friendly BOOLEAN,                   -- Подходит ли для туристов
    local_favorite BOOLEAN,                     -- Любимое место местных
    business_friendly BOOLEAN,                  -- Подходит ли для бизнес-встреч
    fast_service BOOLEAN,                       -- Быстрое обслуживание
    google_rating DECIMAL(2,1),                 -- Рейтинг Google
    tripadvisor_rating DECIMAL(2,1),            -- Рейтинг TripAdvisor
    notable_mentions TEXT[],                    -- Значимые упоминания
    celebrity_visits TEXT[],                    -- Посещения знаменитостей
    press_features TEXT[],                      -- Упоминания в прессе
    customer_quotes TEXT[],                     -- Цитаты клиентов
    hygiene_measures TEXT[],                    -- Меры гигиены
    certifications TEXT[],                      -- Сертификаты
    cleaning_protocol TEXT,                     -- Протокол уборки
    safety_policy TEXT,                         -- Политика безопасности
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,  -- Дата создания записи
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP   -- Дата обновления записи
);

-- Создание индексов для оптимизации запросов
CREATE INDEX idx_users_telegram_id ON users(telegram_user_id);
CREATE INDEX idx_bookings_date ON bookings(date);
CREATE INDEX idx_bookings_restaurant ON bookings(restaurant);
CREATE INDEX idx_restaurants_name ON restaurants(name);
CREATE INDEX idx_restaurants_cuisine ON restaurants(cuisine);
CREATE INDEX idx_restaurants_location ON restaurants(location);
CREATE INDEX idx_restaurants_active ON restaurants(active);

-- Создание функции для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Создание триггера для автоматического обновления updated_at
CREATE TRIGGER update_restaurants_updated_at
    BEFORE UPDATE ON restaurants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 