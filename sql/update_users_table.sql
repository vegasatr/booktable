-- Добавляем новые поля в таблицу users
ALTER TABLE users
ADD COLUMN IF NOT EXISTS budget VARCHAR(50),
ADD COLUMN IF NOT EXISTS last_search_area VARCHAR(100),
ADD COLUMN IF NOT EXISTS last_search_location VARCHAR(100),
ADD COLUMN IF NOT EXISTS preferences_updated_at TIMESTAMP;

-- Создаем индекс для быстрого поиска по telegram_user_id
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_user_id); 