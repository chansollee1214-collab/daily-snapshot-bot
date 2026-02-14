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
from config import TELEGRAM_CHANNELS, CHANNEL_LABELS, KST


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
SESSION_NAME = os.getenv("TG_SESSION")
CHAT_ID = os.getenv("BOT_CHAT_ID")


# -------------------------------------------------
# 리포트 생성
# -------------------------------------------------
async def generate_reports(compact=False):
    user_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await user_client.start()

    data = await collect_telegram(user_client, TELEGRAM_CHANNELS)
    await user_client.disconnect()

    grouped = defaultdict(list)
    for item in data:
        grouped[item["source"]].append(item["text"])

    results = []

    for source, messages in grouped.items():
        summary = summarize_source(source, messages)

        if compact:
            summary = summary[:1000]

        label = CHANNEL_LABELS.get(source, f"📡 {source}")

        formatted = f"""
━━━━━━━━━━━━━━━━━━
*{label}*
━━━━━━━━━━━━━━━━━━

{summary}
"""

        results.append(formatted.strip())

    return results


# -------------------------------------------------
# 수동 명령
# -------------------------------------------------
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 채널별 리포트 생성 중...")

    reports = await generate_reports(compact=False)

    for report_text in reports:
        await update.message.reply_text(
            report_text[:4000],
            parse_mode="Markdown"
        )

    await update.message.reply_text("✅ 완료")


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
            text="🗞️ *Morning Snapshot*\n최근 24시간 채널 요약입니다.",
            parse_mode="Markdown"
        )

        for report_text in reports:
            await application.bot.send_message(
                chat_id=CHAT_ID,
                text=report_text[:4000],
                parse_mode="Markdown"
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