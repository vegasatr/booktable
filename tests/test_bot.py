import requests

# Замените на ваш токен бота
TELEGRAM_BOT_TOKEN = '8123509207:AAHlPsIuxzlB9ZG_TOsE4uDvGWVzywkWF2E'
CHAT_ID = '5419235215'

def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': text
    }
    response = requests.post(url, json=payload)
    return response.json()

def test_bot():
    # Отправляем команду /start
    response = send_message('/start')
    print("Response to /start:", response)

    # Отправляем выбор языка
    response = send_message('1')  # Выбираем русский
    print("Response to language selection:", response)

if __name__ == "__main__":
    test_bot() 