import os
from dotenv import load_dotenv
import requests

# .env 불러오기
load_dotenv()

token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("BOT_CHAT_ID")

url = f"https://api.telegram.org/bot{token}/sendMessage"

response = requests.post(
    url,
    json={
        "chat_id": chat_id,
        "text": "✅ 텔레그램 연결 성공!"
    }
)

print(response.json())