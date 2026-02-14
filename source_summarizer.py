from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_source(source_name, messages):
    combined = "\n\n".join(messages[:100])  # 채널당 최대 100개 제한

    prompt = f"""
    아래는 텔레그램 채널 '{source_name}'의 최근 24시간 메시지다.

    이 채널이 오늘 다룬 내용을 하나의 분석 리포트 형태로 작성하라.

    구성:
    1. 📡 채널명
    2. 오늘 핵심 주제 3~5개 (각 주제는 짧은 소제목 + 설명)
    3. 전반적인 흐름 요약
    4. 채널 특성 한 줄

    조건:
    - 800~1400자 분량
    - Markdown 형식
    - 이모지 적절히 사용
    - 뉴스 나열 금지
    - 채널 내 논의 흐름 중심으로 재구성

    메시지:
    {combined}
    """

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
    )

    return response.output_text