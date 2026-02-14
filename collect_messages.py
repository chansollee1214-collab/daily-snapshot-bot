import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from datetime import datetime, timedelta, timezone

load_dotenv()

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
session_name = os.getenv("TG_SESSION")

# 여기에 네가 모으고 싶은 채널들 입력
channels = [
    "Macrojunglemicrolens",
    "cahier_de_market"
]

since_time = datetime.now(timezone.utc) - timedelta(hours=24)

all_messages = []

with TelegramClient(session_name, api_id, api_hash) as client:
    for channel in channels:
        print(f"\n📡 {channel} 수집 중...")
        
        for message in client.iter_messages(channel):
            if message.date < since_time:
                break
            
            if message.text:
                all_messages.append({
                    "channel": channel,
                    "date": message.date,
                    "text": message.text
                })

print(f"\n총 수집 메시지 수: {len(all_messages)}")

for m in all_messages[:5]:
    print("-----")
    print(m["channel"], m["date"])
    print(m["text"])