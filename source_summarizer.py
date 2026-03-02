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
    """
    모델이 만든 '원문 출처 링크' 섹션/URL 라인을 제거.
    """
    lines = (text or "").splitlines()
    cleaned = []
    in_links_section = False

    for line in lines:
        s = line.strip()

        if s.replace(" ", "") == "원문출처링크":
            in_links_section = True
            continue

        if in_links_section:
            if not s:
                continue
            if s.startswith("http://") or s.startswith("https://"):
                continue
            # 링크 섹션인데 URL이 아닌 텍스트가 나오면 섹션 종료
            in_links_section = False

        # 본문에 섞인 URL 라인도 제거
        if s.startswith("http://") or s.startswith("https://"):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def _ensure_complete_ending(text: str) -> str:
    """
    출력이 '그리고', '또한', '및' 같은 미완성 꼬리로 끝나면 마무리 문장 1줄을 추가.
    """
    t = (text or "").rstrip()
    if not t:
        return t

    bad_endings = (
        "그리고", "또한", "및", "즉", "그래서", "하지만", "다만",
        "핵심 쟁점은", "핵심은", "요약하면", "—", "-", ":", ","
    )

    # 끝이 마침표/종결어미로 끝나는지 대충 체크
    good_terminal = ("다.", "다", "요.", "요", "니다.", "니다", "임.", "함.", ".", "!")
    if t.endswith(good_terminal):
        return t

    for be in bad_endings:
        if t.endswith(be):
            return t + "\n\n전반적으로는 **원칙(윤리)과 통제(안보·정책) 사이의 경계 설정**이 향후 쟁점으로 정리된다."

    # 그 외 애매하게 끊긴 경우도 안전 마감
    return t + "\n\n전반적으로는 논의가 **원칙과 통제권의 균형**으로 수렴한다."


def summarize_source(source_name, messages):
    combined_list = []
    links = []

    for m in messages[:100]:
        text = (m.get("text") or "").strip()
        link = m.get("link")

        if text:
            combined_list.append(text)

        # 링크 수집: 텔레그램은 완전형만, 네이버/기타는 https면 허용
        if link:
            link = link.strip()
            if link.startswith("https://t.me/"):
                if FULL_TME_LINK_RE.match(link):
                    links.append(link)
            else:
                if GENERIC_URL_RE.match(link):
                    links.append(link)

    combined = "\n\n".join(combined_list)

    # ✅ 프롬프트는 네 원본을 최대한 유지하되, 딱 한 줄만 추가(완결 문장 강제)
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
    - 마지막 문장은 반드시 완결된 문장으로 끝내라(‘그리고’, ‘또한’ 등으로 끝내지 마라.)

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

    # ✅ 모델이 만든 링크/링크섹션 제거
    out = _strip_output_links_section(out)

    # ✅ 문장 미완성 마감 방지
    out = _ensure_complete_ending(out)

    # ✅ 우리가 수집한 링크만 다시 붙임
    links = _unique_keep_order(links)[:10]
    if links:
        out += "\n\n원문 출처 링크\n" + "\n".join(links)

    return out