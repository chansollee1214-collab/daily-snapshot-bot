from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def summarize_source(source_name, messages):
    combined = "\n\n".join(messages[:100])

    prompt = f"""
아래는 텔레그램 채널의 최근 24시간 메시지다.

직관적인 브리핑 구조로 정리하라.

형식:

🔥 **핵심 테마 1**
• bullet 3~4개

📉 **핵심 테마 2**
• bullet 2~4개

📌 **기타 포인트**
• bullet 2~3개

조건:
- 채널 특성 설명 금지
- 문단형 서술 금지
- 구조 중심
- 800~1200자
- 이모지는 섹션 제목에만 사용
- 뉴스 나열 금지, 공통 주제로 묶기

메시지:
{combined}
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
    )

    return response.output_text