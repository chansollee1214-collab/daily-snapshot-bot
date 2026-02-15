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
    3. 전반적인 핵심 흐름 요약

    조건:
    - 800~1400자 분량
    - HTML 형식
    - 이모지 적절히 사용
    - 뉴스 나열 금지
    - 채널 내 논의 흐름 중심으로 재구성
    - 어려운 경제, 기술용어는 쉽게 풀어 설명
    - 채널 링크도 하단에 첨부

    아래는 텔레그램 채널의 최근 24시간 메시지다.

    ⚠️ 절대 HTML 태그를 사용하지 마라.
    ⚠️ <html>, <body>, <ul>, <li>, <p> 등 어떤 태그도 쓰지 마라.
    ⚠️ Markdown도 쓰지 마라.
    ⚠️ 굵게 표시도 하지 마라.
    ⚠️ 오직 순수 텍스트만 사용하라.
    대신 문단구분 및 문단과 문단사이 한줄 띄우기를 통해 글의 가독성을 높여라

    메시지:
    {combined}
    """

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
    )

    return response.output_text