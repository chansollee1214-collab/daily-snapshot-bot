import os
import asyncio
import logging
from datetime import datetime, timedelta
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

# 로그 (배포 환경 로그에서 daily_loop 예외 확인 가능)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------
# 텍스트 안전 분할 + 레이트리밋 대응 (4096자 제한)
# -------------------------------------------------
async def safe_send(bot, chat_id, text):
    for i in range(0, len(text), 4000):
        chunk = text[i:i + 4000]
        while True:
            try:
                await bot.send_message(chat_id=chat_id, text=chunk)
                break
            except RetryAfter as e:
                wait = int(getattr(e, "retry_after", 3)) + 1
                logger.warning("RetryAfter 발생. %s초 대기 후 재시도", wait)
                await asyncio.sleep(wait)


# -------------------------------------------------
# 리포트 생성 공통 함수
# -------------------------------------------------
async def generate_reports(compact=False):
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

    results = []

    # Telegram
    if telegram_grouped:
        results.append("━━━━━━━━━━━━━━━━━━\n📡 Telegram Channel Brief\n━━━━━━━━━━━━━━━━━━")

        for source, messages in telegram_grouped.items():
            summary = summarize_source(source, messages)
            if compact:
                summary = summary[:1000]

            label = CHANNEL_LABELS.get(source, f"📡 {source}")

            formatted = f"""
{label}

{summary}
"""
            results.append(formatted.strip())

    # Naver
    if naver_grouped:
        results.append("\n━━━━━━━━━━━━━━━━━━\n📝 Naver Blog Brief\n━━━━━━━━━━━━━━━━━━")

        for blog_id, messages in naver_grouped.items():
            summary = summarize_source(blog_id, messages)
            if compact:
                summary = summary[:1000]

            label = NAVER_BLOGS.get(blog_id, f"📝 {blog_id}")

            formatted = f"""
{label}

{summary}
"""
            results.append(formatted.strip())

    return results


# -------------------------------------------------
# (추가) 자동 리포트 1회 전송 공통 로직
# -------------------------------------------------
async def send_morning_snapshot(bot, chat_id, compact=True, is_test=False):
    reports = await generate_reports(compact=compact)

    title = "🗞️ Morning Snapshot"
    if is_test:
        title += " (TEST)"

    await bot.send_message(
        chat_id=chat_id,
        text=f"{title}\n최근 24시간 채널 + 블로그 요약입니다."
    )

    for report_text in reports:
        await safe_send(bot, chat_id, report_text)

    end_msg = "☀️ 좋은 하루 보내세요."
    if is_test:
        end_msg += " (TEST)"

    await bot.send_message(chat_id=chat_id, text=end_msg)


# -------------------------------------------------
# 수동 명령 (/report)
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

        await update.message.reply_text(
            f"📡 {current}/{total_sources} 분석 중...\n{source}"
        )

        summary = summarize_source(source, messages)
        label = CHANNEL_LABELS.get(source, f"📡 {source}")

        formatted = f"""
━━━━━━━━━━━━━━━━━━
{label}
━━━━━━━━━━━━━━━━━━

{summary}
"""
        await update.message.reply_text(formatted[:4000])

    # Naver
    for blog_id, messages in naver_grouped.items():
        current += 1

        await update.message.reply_text(
            f"📝 {current}/{total_sources} 분석 중...\n{blog_id}"
        )

        summary = summarize_source(blog_id, messages)
        label = NAVER_BLOGS.get(blog_id, f"📝 {blog_id}")

        formatted = f"""
━━━━━━━━━━━━━━━━━━
{label}
━━━━━━━━━━━━━━━━━━

{summary}
"""
        await update.message.reply_text(formatted[:4000])

    await update.message.reply_text("✅ 모든 소스 분석 완료")


# -------------------------------------------------
# (추가) 지금 당장 자동 리포트 테스트 실행: /test_daily
#  - 기본: 명령 친 채팅으로 전송
#  - /test_daily prod : BOT_CHAT_ID로 전송
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
            await update.message.reply_text("❌ BOT_CHAT_ID가 비어있어서 prod 테스트를 할 수 없습니다.")
            return
        dest_chat_id = CHAT_ID
        mode = "BOT_CHAT_ID"

    await update.message.reply_text(
        "🧪 자동 리포트 테스트 시작\n"
        f"- KST 현재: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 다음 자동 실행: {next_run.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 전송 모드: {mode}\n"
        f"- 전송 대상 chat_id: {dest_chat_id}\n"
        "⏳ 수집/요약 중..."
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
# 오전 7시 자동 실행 (안 죽게 안정화)
# -------------------------------------------------
async def daily_loop(application):
    while True:
        try:
            if not CHAT_ID:
                logger.error("BOT_CHAT_ID가 비어있습니다. 자동 리포트를 보낼 수 없습니다.")
                await asyncio.sleep(60)
                continue

            now = datetime.now(KST)
            target = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)

            wait_seconds = max(0, (target - now).total_seconds())
            logger.info("⏳ 다음 자동 실행까지 %s초 대기 (KST 목표: %s)", int(wait_seconds), target.isoformat())
            await asyncio.sleep(wait_seconds)

            logger.info("⏰ 오전 7시 자동 리포트 실행")
            await send_morning_snapshot(
                bot=application.bot,
                chat_id=CHAT_ID,
                compact=True,
                is_test=False
            )

        except Exception:
            logger.exception("daily_loop에서 예외 발생. 60초 후 재시도")
            await asyncio.sleep(60)


# -------------------------------------------------
# 실행
# -------------------------------------------------
async def post_init(application):
    # PTB가 관리하는 task로 등록 (예외/취소 처리 안정)
    application.create_task(daily_loop(application))


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("test_daily", test_daily))

    print("🤖 봇 실행 중...")
    app.run_polling()


if __name__ == "__main__":
    main()