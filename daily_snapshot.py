import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from datetime import datetime, timedelta, timezone
from openai import OpenAI
import requests

load_dotenv()

api_id = int(os.getenv("TG_API_ID"))
api_hash = os.getenv("TG_API_HASH")
session_name = os.getenv("TG_SESSION")

bot_token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("BOT_CHAT_ID")
openai_key = os.getenv("OPENAI_API_KEY")

channels = [
    "Macrojunglemicrolens",
    "cahier_de_market"
]

since_time = datetime.now(timezone.utc) - timedelta(hours=24)

all_text = []

# 1️⃣ 텔레그램 수집
with TelegramClient(session_name, api_id, api_hash) as client:
    for channel in channels:
        for message in client.iter_messages(channel):
            if message.date < since_time:
                break
            if message.text:
                all_text.append(message.text)

print(f"수집 메시지 수: {len(all_text)}")

# 2️⃣ 텍스트 합치기
combined_text = "\n\n".join(all_text[:200])  # 너무 많으면 200개만

# 3️⃣ OpenAI 요약
client = OpenAI(api_key=openai_key)

prompt = f"""
너는 투자 전략가다.

아래는 지난 24시간 텔레그램 뉴스다.

단순 요약이 아니라,
'오늘 시장이 어떻게 움직이고 있는지'
내러티브 중심 전략 리포트를 작성하라.

구성:

1. 오늘의 한 줄 결론
2. 핵심 테마 3~5개 (각 테마는:
   - 무슨 일이 일어났는지
   - 왜 중요한지
   - 어떤 섹터/종목에 영향인지
   - 시장 반응)
3. 섹터 간 연결 구조
4. 리스크 요인
5. 내일 체크포인트

조건:
- 한국어
- 나열 금지 (서술형 중심)
- 중요도 높은 내용 위주
- 불확실한 것은 명확히 불확실하다고 표현
- 과장 금지
- 총 900~1200자 이내.
- 각 테마는 5~6줄 이내.
- 문단을 짧게 유지.
- 각 테마 마지막에 '→ 그래서 무엇을 볼 것인가' 한 줄로 정리하라.
- 각 테마 제목은 강한 문장형으로 작성하라.
- 숫자는 핵심 5~6개만 남기고 나머지는 제거하라.
- 텔레그램용 Markdown 사용
- 주요 문장은 **볼드**
- 섹션 앞에는 이모지 사용
- 문단은 3줄 이하
- 각 테마는 짧은 bullet 구조
- 마지막 줄에 👉 행동 포인트 추가

뉴스:
{combined_text}
"""

response = client.responses.create(
    model="gpt-5.2",
    input=prompt,
)

summary = response.output_text

print("요약 완료")

# 4️⃣ 텔레그램으로 전송
url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
requests.post(
    url,
    json={
        "chat_id": chat_id,
        "text": summary,
        "parse_mode": "Markdown"
    }
)

print("텔레그램 전송 완료")