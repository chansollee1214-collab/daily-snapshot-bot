import os
from dotenv import load_dotenv
from telegram_collector import collect_telegram
from source_summarizer import summarize_source
from config import TELEGRAM_CHANNELS
from collections import defaultdict
import requests

load_dotenv()

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
session_name = os.getenv("TG_SESSION")

bot_token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("BOT_CHAT_ID")

def send_message(text):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text[:4000],
            "parse_mode": "Markdown"
        }
    )

# 수집
data = collect_telegram(
    TELEGRAM_CHANNELS,
    api_id,
    api_hash,
    session_name
)

# 채널별 그룹핑
grouped = defaultdict(list)
for item in data:
    grouped[item["source"]].append(item["text"])

# 채널별 리포트 생성 및 전송
for source, messages in grouped.items():
    report = summarize_source(source, messages)
    send_message(report)