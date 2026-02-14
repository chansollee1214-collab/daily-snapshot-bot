import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient

load_dotenv()

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
session_name = os.getenv("TG_SESSION")

channel_username = "Macrojunglemicrolens"  # ← 여기에 채널 username 입력

with TelegramClient(session_name, api_id, api_hash) as client:
    print("채널에서 최근 메시지 5개 가져오는 중...\n")

    for message in client.iter_messages(channel_username, limit=5):
        print("-----")
        print(message.date)
        print(message.text)