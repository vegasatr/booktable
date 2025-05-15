-- Скрипт миграции базы данных BookTable
-- Версия: 1.0.0
-- Дата: 2024-03-15
-- Описание: Добавляет поле telegram_username и переносит данные из client_name
--
-- Изменения:
-- 1. Добавлено новое поле telegram_username для хранения имени пользователя из Telegram
-- 2. Перенос данных из client_name в telegram_username
-- 3. Очистка поля client_name для последующего заполнения при первом заказе
--
-- Использование:
--     psql -h /var/run/postgresql -U root -d booktable -f scripts/migrate_db.sql
--
-- Требования:
-- - PostgreSQL должен быть запущен
-- - База данных booktable должна существовать
-- - Пользователь root должен иметь права на изменение таблицы users

-- Добавляем новое поле telegram_username
ALTER TABLE users ADD COLUMN telegram_username VARCHAR(255);

-- Переносим данные из client_name в telegram_username
-- Это нужно сделать до очистки client_name
UPDATE users SET telegram_username = client_name WHERE telegram_username IS NULL;

-- Очищаем поле client_name, так как оно будет заполняться позже
-- при первом заказе пользователя
UPDATE users SET client_name = NULL; 