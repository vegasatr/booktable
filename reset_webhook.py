import requests

token = "8123509207:AAHlPsIuxzlB9ZG_TOsE4uDvGWVzywkWF2E"
url = f"https://api.telegram.org/bot{token}/deleteWebhook"

response = requests.get(url)
print(response.json())