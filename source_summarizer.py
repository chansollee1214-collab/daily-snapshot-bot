from openai import OpenAI
import os
import re
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 텔레그램 완전형 링크
FULL_TME_LINK_RE = re.compile(r"^https://t\.me/(?:c/\d+|[A-Za-z0-9_]+)/\d+$")

# 일반 URL (네이버 등)
GENERIC_URL_RE = re.compile(r"^https?://\S+$")


def _unique_keep_order(items):
    seen = set()
    out = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _strip_output_links_section(text: str) -> str:
    lines = (text or "").splitlines()
    cleaned = []
    in_links_section = False

    for line in lines:
        s = line.strip()

        # 모델이 만든 원문 링크 섹션 제거
        if s.replace(" ", "") == "원문출처링크":
            in_links_section = True
            continue

        if in_links_section:
            if not s:
                continue
            if s.startswith("http"):
                continue
            in_links_section = False

        # 본문에 URL이 섞이면 제거
        if s.startswith("http"):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def summarize_source(source_name, messages):
    combined_list = []
    links = []

    for m in messages[:100]:
        text = m.get("text", "")
        link = m.get("link")

        if text:
            combined_list.append(text)

        # 🔥 핵심 수정 부분
        if link:
            link = link.strip()

            # 텔레그램 링크는 완전형만
            if link.startswith("https://t.me/"):
                if FULL_TME_LINK_RE.match(link):
                    links.append(link)

            # 네이버/기타는 그냥 https URL이면 허용
            else:
                if GENERIC_URL_RE.match(link):
                    links.append(link)

    combined = "\n\n".join(combined_list)

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
    - 참고한 링크도 하단에 첨부(참고 링크는 반드시 "원문 출처 링크" 섹션에 제공된 URL만 사용하라.메시지 본문에 포함된 URL은 절대 참고 링크로 포함하지 마라.새로운 URL을 생성하지 마라.)

    아래는 텔레그램 채널의 최근 24시간 메시지다.

    ⚠️ 절대 HTML 태그를 사용하지 마라.
    ⚠️ Markdown도 쓰지 마라.
    ⚠️ 굵게 표시도 하지 마라.
    ⚠️ 오직 순수 텍스트만 사용하라.

    메시지:
    {combined}
    """

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
    )

    out = (response.output_text or "").strip()

    # 모델이 만든 링크 제거
    out = _strip_output_links_section(out)

    # 우리가 수집한 링크만 붙임
    links = _unique_keep_order(links)

    if links:
        out += "\n\n원문 출처 링크\n" + "\n".join(links)

    return out