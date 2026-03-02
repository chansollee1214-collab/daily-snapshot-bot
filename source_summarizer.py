from openai import OpenAI
import os
import re
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 완전형 텔레그램 링크만 허용
# - 공개채널: https://t.me/username/12345
# - 내부링크: https://t.me/c/123456789/12345
FULL_TME_LINK_RE = re.compile(r"^https://t\.me/(?:c/\d+|[A-Za-z0-9_]+)/\d+$")


def _unique_keep_order(items):
    seen = set()
    out = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _strip_output_links_section(text: str) -> str:
    """
    모델이 출력한 '원문 출처 링크' 섹션(및 URL 라인)을 제거해서
    우리가 가진 링크 목록으로 다시 붙일 수 있게 함.
    """
    lines = (text or "").splitlines()
    cleaned = []
    in_links_section = False

    for line in lines:
        s = line.strip()

        # '원문 출처 링크' 섹션 시작 감지
        if s.replace(" ", "") == "원문출처링크":
            in_links_section = True
            continue

        # 링크 섹션 안에서는 URL/빈줄만 스킵하고, 다른 텍스트가 나오면 섹션 종료
        if in_links_section:
            if not s:
                continue
            if s.startswith("http://") or s.startswith("https://"):
                continue
            # 링크 섹션인데 URL이 아닌 텍스트가 나오면 섹션 종료하고 그 라인은 본문으로 살림
            in_links_section = False

        # 섹션 밖에서도 URL 라인이 섞이면 제거(가끔 모델이 본문에 URL을 넣음)
        if s.startswith("http://") or s.startswith("https://"):
            continue

        cleaned.append(line)

    # 뒤쪽 공백 정리
    return "\n".join(cleaned).strip()


def summarize_source(source_name, messages):
    combined_list = []

    # ✅ 우리가 붙일 "정확한 링크"는 따로 모아둠
    links = []

    for m in messages[:100]:
        text = m["text"]
        link = m.get("link")

        if link:
            combined_list.append(f"{text}\n(출처: {link})")
            # 완전형 링크만 저장
            if FULL_TME_LINK_RE.match(link.strip()):
                links.append(link.strip())
        else:
            combined_list.append(text)

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

    out = (response.output_text or "").strip()

    # ✅ (핵심) 모델이 만든 '원문 출처 링크' 섹션/URL 라인 제거
    out = _strip_output_links_section(out)

    # ✅ 링크는 우리가 가진 것만 "정확히" 다시 붙이기
    links = _unique_keep_order(links)[:10]  # 너무 길어지면 상위 10개만
    if links:
        out += "\n\n원문 출처 링크\n" + "\n".join(links)

    return out