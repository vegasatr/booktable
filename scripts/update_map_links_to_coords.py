import psycopg2
import re

# Подключение к базе данных (настройки как в main.py)
def get_db_connection():
    return psycopg2.connect(
        dbname="booktable",
        user="root",
        host="/var/run/postgresql"
    )

def extract_coords_from_gmaps(url):
    """
    Извлекает координаты из ссылки Google Maps.
    Поддерживает форматы:
    - https://www.google.com/maps/place/.../@7.778123,98.303456,...
    - https://maps.google.com/?q=7.778123,98.303456
    - https://goo.gl/maps/... (не поддерживается, нужен резолвинг редиректа)
    """
    # Формат @lat,lon
    m = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if m:
        return f"{m.group(1)},{m.group(2)}"
    # Формат ?q=lat,lon
    m = re.search(r'[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if m:
        return f"{m.group(1)},{m.group(2)}"
    return None

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, map_link FROM restaurants WHERE map_link IS NOT NULL AND map_link != ''")
    rows = cur.fetchall()
    updated = 0
    for rid, link in rows:
        coords = extract_coords_from_gmaps(link)
        if coords:
            cur.execute("UPDATE restaurants SET map_link = %s WHERE id = %s", (coords, rid))
            updated += 1
            print(f"id={rid}: {link} -> {coords}")
        else:
            print(f"id={rid}: не удалось извлечь координаты из {link}")
    conn.commit()
    cur.close()
    conn.close()
    print(f"Готово! Обновлено записей: {updated}")

if __name__ == "__main__":
    main() 