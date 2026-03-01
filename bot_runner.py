import os
import asyncio
import logging
from datetime import datetime, timedelta, time as dtime
from collections import defaultdict
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import RetryAfter

from telethon import TelegramClient

from telegram_collector import collect_telegram
from source_summarizer import summarize_source
from config import TELEGRAM_CHANNELS, CHANNEL_LABELS, NAVER_BLOGS, KST
from naver_collector import collect_naver

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
SESSION_NAME = os.getenv("TG_SESSION")

# BOT_CHAT_ID: 숫자 ID(-100...) 또는 @채널username 모두 허용
_CHAT_ID_RAW = os.getenv("BOT_CHAT_ID")
if _CHAT_ID_RAW and _CHAT_ID_RAW.lstrip("-").isdigit():
    CHAT_ID = int(_CHAT_ID_RAW)
else:
    CHAT_ID = _CHAT_ID_RAW

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# (권장) httpx가 매 요청 URL을 찍어서 토큰이 노출될 수 있어 WARNING으로 낮춤
logging.getLogger("httpx").setLevel(logging.WARNING)


# -------------------------------------------------
# 텍스트 안전 분할 + 레이트리밋 대응 (URL 중간 절단 방지)
# -------------------------------------------------
async def safe_send(bot, chat_id, text, limit=4000):
    """
    텔레그램 메시지 길이 제한 대응.
    - 가능한 한 줄바꿈(\n) 기준으로 쪼개서 URL이 중간에서 잘리는 문제를 줄임.
    - 줄바꿈이 없으면 공백 기준으로 자름.
    - 그마저도 없으면(limit보다 긴 단일 토큰) 어쩔 수 없이 limit에서 자름.
    """
    remaining = (text or "").strip()
    while remaining:
        if len(remaining) <= limit:
            await bot.send_message(chat_id=chat_id, text=remaining)
            return

        # limit 이내에서 가장 마지막 줄바꿈 우선
        cut = remaining.rfind("\n", 0, limit)

        # 줄바꿈이 없다면 공백 기준으로
        if cut < 0:
            cut = remaining.rfind(" ", 0, limit)

        # 너무 앞에서 끊기면 비효율적이라 fallback
        if cut < 0 or cut < int(limit * 0.6):
            cut = limit

        chunk = remaining[:cut].rstrip()
        remaining = remaining[cut:].lstrip()

        # 레이트리밋 대응
        while True:
            try:
                await bot.send_message(chat_id=chat_id, text=chunk)
                break
            except RetryAfter as e:
                wait = int(getattr(e, "retry_after", 3)) + 1
                logger.warning("RetryAfter 발생. %s초 대기 후 재시도", wait)
                await asyncio.sleep(wait)


# -------------------------------------------------
# (스트리밍) 채널/블로그 1개 끝날 때마다 바로 yield
# -------------------------------------------------
async def generate_reports_stream(compact=False):
    user_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await user_client.start()

    try:
        telegram_data = await collect_telegram(user_client, TELEGRAM_CHANNELS)
        naver_data = await collect_naver(NAVER_BLOGS)
    finally:
        await user_client.disconnect()

    telegram_grouped = defaultdict(list)
    for item in telegram_data:
        telegram_grouped[item["source"]].append(item)

    naver_grouped = defaultdict(list)
    for item in naver_data:
        naver_grouped[item["source"]].append(item)

    # Telegram
    if telegram_grouped:
        yield "━━━━━━━━━━━━━━━━━━\n📡 Telegram Channel Brief\n━━━━━━━━━━━━━━━━━━"

        for source, messages in telegram_grouped.items():
            logger.info("요약 생성 중 (Telegram): %s", source)

            summary = summarize_source(source, messages)
            if compact:
                summary = summary[:1000]

            label = CHANNEL_LABELS.get(source, f"📡 {source}")
            yield f"{label}\n\n{summary}".strip()

    # Naver
    if naver_grouped:
        yield "━━━━━━━━━━━━━━━━━━\n📝 Naver Blog Brief\n━━━━━━━━━━━━━━━━━━"

        for blog_id, messages in naver_grouped.items():
            logger.info("요약 생성 중 (Naver): %s", blog_id)

            summary = summarize_source(blog_id, messages)
            if compact:
                summary = summary[:1000]

            label = NAVER_BLOGS.get(blog_id, f"📝 {blog_id}")
            yield f"{label}\n\n{summary}".strip()


# -------------------------------------------------
# 자동 리포트: 스트리밍 전송 (한 소스 끝날 때마다 바로 보내기)
# -------------------------------------------------
async def send_morning_snapshot(bot, chat_id, compact=True, is_test=False):
    title = "🗞️ Morning Snapshot"
    if is_test:
        title += " (TEST)"

    await bot.send_message(
        chat_id=chat_id,
        text=f"{title}\n⏳ 소스별로 요약이 완성되는 즉시 순차 전송합니다."
    )

    sent_blocks = 0
    async for report_text in generate_reports_stream(compact=compact):
        await safe_send(bot, chat_id, report_text)
        sent_blocks += 1

    await bot.send_message(
        chat_id=chat_id,
        text=f"✅ 전송 완료! (총 {sent_blocks}개 블록)"
    )

    end_msg = "☀️ 좋은 하루 보내세요."
    if is_test:
        end_msg += " (TEST)"
    await bot.send_message(chat_id=chat_id, text=end_msg)


# -------------------------------------------------
# /chatid : 지금 채팅방의 chat_id 확인용
# -------------------------------------------------
async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🆔 이 채팅의 chat_id: {cid}\n"
        f"→ 이 값을 Railway Variables의 BOT_CHAT_ID에 넣으면 자동 리포트가 이 채팅으로 갑니다."
    )


# -------------------------------------------------
# 수동 명령 (/report) - 기존 동작 유지
# -------------------------------------------------
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 리포트 준비 중...")

    user_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await user_client.start()

    telegram_data = await collect_telegram(user_client, TELEGRAM_CHANNELS)
    naver_data = await collect_naver(NAVER_BLOGS)

    await user_client.disconnect()

    telegram_grouped = defaultdict(list)
    for item in telegram_data:
        telegram_grouped[item["source"]].append(item)

    naver_grouped = defaultdict(list)
    for item in naver_data:
        naver_grouped[item["source"]].append(item)

    total_sources = len(telegram_grouped) + len(naver_grouped)

    await update.message.reply_text(
        f"📊 총 {total_sources}개 소스 분석 시작\n"
        f"예상 소요: 약 {total_sources * 8}~{total_sources * 12}초"
    )

    current = 0

    # Telegram
    for source, messages in telegram_grouped.items():
        current += 1
        await update.message.reply_text(f"📡 {current}/{total_sources} 분석 중...\n{source}")

        summary = summarize_source(source, messages)
        label = CHANNEL_LABELS.get(source, f"📡 {source}")

        formatted = f"""
━━━━━━━━━━━━━━━━━━
{label}
━━━━━━━━━━━━━━━━━━

{summary}
"""
        await safe_send(context.bot, update.effective_chat.id, formatted)

    # Naver
    for blog_id, messages in naver_grouped.items():
        current += 1
        await update.message.reply_text(f"📝 {current}/{total_sources} 분석 중...\n{blog_id}")

        summary = summarize_source(blog_id, messages)
        label = NAVER_BLOGS.get(blog_id, f"📝 {blog_id}")

        formatted = f"""
━━━━━━━━━━━━━━━━━━
{label}
━━━━━━━━━━━━━━━━━━

{summary}
"""
        await safe_send(context.bot, update.effective_chat.id, formatted)

    await update.message.reply_text("✅ 모든 소스 분석 완료")


# -------------------------------------------------
# /test_daily : 지금 당장 자동리포트 1회 테스트
# -------------------------------------------------
async def test_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(KST)
    next_run = now.replace(hour=7, minute=0, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)

    dest_chat_id = update.effective_chat.id
    mode = "THIS_CHAT"

    if context.args and context.args[0].lower() in ("prod", "real", "chatid"):
        if not CHAT_ID:
            await update.message.reply_text(
                "❌ BOT_CHAT_ID가 비어있어서 prod 테스트를 할 수 없습니다.\n"
                "먼저 /chatid로 값 확인 후 BOT_CHAT_ID를 세팅하세요."
            )
            return
        dest_chat_id = CHAT_ID
        mode = "BOT_CHAT_ID"

    await update.message.reply_text(
        "🧪 자동 리포트 테스트 시작\n"
        f"- KST 현재: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 다음 자동 실행: {next_run.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 전송 모드: {mode}\n"
        f"- 전송 대상 chat_id: {dest_chat_id}\n"
        "⏳ 수집/요약 중... (완성되는 소스부터 순차 전송됩니다)"
    )

    try:
        await send_morning_snapshot(
            bot=context.bot,
            chat_id=dest_chat_id,
            compact=True,
            is_test=True
        )
        await update.message.reply_text("✅ 테스트 전송 완료")
    except Exception as e:
        logger.exception("test_daily 실패")
        await update.message.reply_text(f"❌ 테스트 실패: {type(e).__name__}: {e}")


# -------------------------------------------------
# 오전 7시 자동 실행 (JobQueue)
# -------------------------------------------------
async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        logger.error("BOT_CHAT_ID가 비어있습니다. 자동 리포트를 보낼 수 없습니다.")
        return

    logger.info("⏰ 오전 7시 자동 리포트 실행 (JobQueue)")
    await send_morning_snapshot(
        bot=context.bot,
        chat_id=CHAT_ID,
        compact=True,
        is_test=False
    )


async def post_init(application):
    if application.job_queue is None:
        logger.error(
            "JobQueue가 활성화되어 있지 않습니다. requirements.txt에서 "
            "python-telegram-bot[job-queue]==20.7 설치가 필요합니다."
        )
        return

    application.job_queue.run_daily(
        daily_job,
        time=dtime(hour=7, minute=0, tzinfo=KST),
        name="daily_morning_snapshot",
    )
    logger.info("✅ JobQueue 등록 완료: 매일 KST 07:00 자동 리포트")


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("test_daily", test_daily))
    app.add_handler(CommandHandler("chatid", chatid))

    print("🤖 봇 실행 중...")
    app.run_polling()


if __name__ == "__main__":
    main()