import os
from dotenv import load_dotenv
from telegram_collector import collect_telegram
from config import TELEGRAM_CHANNELS

load_dotenv()

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
session_name = os.getenv("TG_SESSION")

data = collect_telegram(
    TELEGRAM_CHANNELS,
    api_id,
    api_hash,
    session_name
)

print(f"총 수집 개수: {len(data)}\n")

for item in data[:5]:
    print("-----")
    print(item["source"])
    print(item["date"])
    print(item["text"][:100])