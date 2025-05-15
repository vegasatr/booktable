-- Создание таблицы Users
CREATE TABLE users (
    client_number SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    client_name VARCHAR(255),
    phone VARCHAR(50),
    check_preference VARCHAR(10),
    language VARCHAR(10) NOT NULL
);

-- Создание таблицы Bookings
CREATE TABLE bookings (
    booking_number SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time TIME NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    guests INTEGER NOT NULL,
    restaurant VARCHAR(255) NOT NULL,
    booking_method VARCHAR(50),
    restaurant_contact VARCHAR(255),
    preferences TEXT,
    client_code VARCHAR(50),
    discount DECIMAL(5,2),
    status VARCHAR(50) NOT NULL,
    comment TEXT
);

-- Создание таблицы Restaurants
CREATE TABLE restaurants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    cuisine VARCHAR(255),
    location VARCHAR(255),
    atmosphere TEXT,
    average_check DECIMAL(10,2),
    features TEXT[],
    working_hours JSONB,
    booking_method VARCHAR(50),
    booking_contact VARCHAR(255),
    active BOOLEAN DEFAULT true,
    discount DECIMAL(5,2),
    key_dishes TEXT[],
    michelin BOOLEAN,
    map_link TEXT,
    meal_types TEXT[],
    service_options TEXT[],
    dietary_options TEXT[],
    occasions TEXT[],
    drinks_entertainment TEXT[],
    accessibility TEXT[],
    address TEXT,
    phone VARCHAR(50),
    website TEXT,
    instagram TEXT,
    tripadvisor_link TEXT,
    reservation_required BOOLEAN,
    payment_methods TEXT[],
    wifi BOOLEAN,
    languages_spoken TEXT[],
    menu_languages TEXT[],
    menu_options TEXT[],
    spicy_dishes BOOLEAN,
    kids_menu BOOLEAN,
    portion_size VARCHAR(50),
    customizable_dishes BOOLEAN,
    dish_of_the_day BOOLEAN,
    organic_local_ingredients BOOLEAN,
    tasting_menu BOOLEAN,
    takeaway_available BOOLEAN,
    delivery_options TEXT[],
    catering_available BOOLEAN,
    allergen_info TEXT,
    product_source_info TEXT,
    sustainability_policy TEXT,
    drink_specials TEXT[],
    corkage_fee DECIMAL(10,2),
    wine_list TEXT[],
    cocktails TEXT[],
    non_alcoholic_drinks TEXT[],
    coffee_tea_options TEXT[],
    sommelier_available BOOLEAN,
    noise_level VARCHAR(50),
    outdoor_seating BOOLEAN,
    view TEXT[],
    air_conditioning BOOLEAN,
    smoking_area BOOLEAN,
    pet_friendly BOOLEAN,
    child_friendly BOOLEAN,
    kids_area BOOLEAN,
    high_chairs BOOLEAN,
    animation_family_entertainment BOOLEAN,
    dress_code VARCHAR(255),
    power_sockets BOOLEAN,
    qr_menu BOOLEAN,
    mobile_app BOOLEAN,
    online_chat_available BOOLEAN,
    private_dining BOOLEAN,
    group_friendly BOOLEAN,
    event_support BOOLEAN,
    gift_cards BOOLEAN,
    holiday_specials BOOLEAN,
    romantic BOOLEAN,
    instagrammable BOOLEAN,
    chef_interaction BOOLEAN,
    unique_features TEXT[],
    story_or_concept TEXT,
    nearby_landmarks TEXT[],
    popular_with TEXT[],
    solo_friendly BOOLEAN,
    senior_friendly BOOLEAN,
    tourist_friendly BOOLEAN,
    local_favorite BOOLEAN,
    business_friendly BOOLEAN,
    fast_service BOOLEAN,
    google_rating DECIMAL(2,1),
    tripadvisor_rating DECIMAL(2,1),
    notable_mentions TEXT[],
    celebrity_visits TEXT[],
    press_features TEXT[],
    customer_quotes TEXT[],
    hygiene_measures TEXT[],
    certifications TEXT[],
    cleaning_protocol TEXT,
    safety_policy TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов
CREATE INDEX idx_users_telegram_id ON users(telegram_user_id);
CREATE INDEX idx_bookings_date ON bookings(date);
CREATE INDEX idx_bookings_restaurant ON bookings(restaurant);
CREATE INDEX idx_restaurants_name ON restaurants(name);
CREATE INDEX idx_restaurants_cuisine ON restaurants(cuisine);
CREATE INDEX idx_restaurants_location ON restaurants(location);
CREATE INDEX idx_restaurants_active ON restaurants(active);

-- Создание триггера для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_restaurants_updated_at
    BEFORE UPDATE ON restaurants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 