import os
from dotenv import load_dotenv
from telegram_collector import collect_telegram
from config import TELEGRAM_CHANNELS
from source_summarizer import summarize_source
from collections import defaultdict

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

grouped = defaultdict(list)

for item in data:
    grouped[item["source"]].append(item["text"])

for source, messages in grouped.items():
    print(f"\n===== {source} 요약 시작 =====\n")
    summary = summarize_source(source, messages)
    print(summary)