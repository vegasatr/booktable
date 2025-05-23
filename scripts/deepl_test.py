import requests
import sys

DEEPL_API_KEY = "885838b0-fa43-48b3-b7e8-9de4d9fb874c:fx"
DEEPL_URL = "https://api-free.deepl.com/v2/translate"

# Получаем текст и язык из аргументов командной строки
text = sys.argv[1] if len(sys.argv) > 1 else "Please send your location:"
target_lang = sys.argv[2] if len(sys.argv) > 2 else "RU"

params = {
    "text": text,
    "target_lang": target_lang
}
headers = {
    "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"
}

response = requests.post(DEEPL_URL, data=params, headers=headers)

try:
    data = response.json()
    print(f"Перевод '{text}' на {target_lang}:", data)
    if "translations" in data:
        print("Перевод:", data["translations"][0]["text"])
    else:
        print("Ошибка или неожиданный ответ Deepl API.")
except Exception as e:
    print("Ошибка при обработке ответа:", e)
    print("Сырой ответ:", response.text) 