import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient

load_dotenv()

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
session_name = os.getenv("TG_SESSION")

with TelegramClient(session_name, api_id, api_hash) as client:
    print("✅ 텔레그램 로그인 성공!")
    me = client.get_me()
    print("내 계정:", me.username)