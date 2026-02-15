import os
import asyncio
from datetime import datetime, timedelta, time as dtime
from collections import defaultdict
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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
CHAT_ID = os.getenv("BOT_CHAT_ID")


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
        telegram_grouped[item["source"]].append(item["text"])

    naver_grouped = defaultdict(list)
    for item in naver_data:
        naver_grouped[item["source"]].append(item["text"])

    results = []

    # Telegram 섹션
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

    # Naver 섹션
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
        telegram_grouped[item["source"]].append(item["text"])

    naver_grouped = defaultdict(list)
    for item in naver_data:
        naver_grouped[item["source"]].append(item["text"])

    total_sources = len(telegram_grouped) + len(naver_grouped)

    await update.message.reply_text(
        f"📊 총 {total_sources}개 소스 분석 시작\n"
        f"예상 소요: 약 {total_sources * 8}~{total_sources * 12}초"
    )

    current = 0

    # Telegram 처리
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

    # Naver 처리
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
# 오전 7시 자동 실행
# -------------------------------------------------
async def daily_loop(application):
    while True:
        now = datetime.now(KST)
        target = datetime.combine(now.date(), dtime(7, 0, tzinfo=KST))

        if now >= target:
            target = target + timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        print(f"⏳ 다음 자동 실행까지 {int(wait_seconds)}초 대기")

        await asyncio.sleep(wait_seconds)

        print("⏰ 오전 7시 자동 리포트 실행")

        reports = await generate_reports(compact=True)

        await application.bot.send_message(
            chat_id=CHAT_ID,
            text="🗞️ Morning Snapshot\n최근 24시간 채널 + 블로그 요약입니다."
        )

        for report_text in reports:
            await application.bot.send_message(
                chat_id=CHAT_ID,
                text=report_text[:4000]
            )

        await application.bot.send_message(
            chat_id=CHAT_ID,
            text="☀️ 좋은 하루 보내세요."
        )


# -------------------------------------------------
# 실행
# -------------------------------------------------
async def post_init(application):
    asyncio.create_task(daily_loop(application))


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("report", report))

    print("🤖 봇 실행 중...")
    app.run_polling()


if __name__ == "__main__":
    main()