from datetime import datetime, timedelta
from config import KST


async def collect_telegram(client, channels):
    cutoff = datetime.now(KST) - timedelta(hours=24)
    results = []

    for channel in channels:
        async for message in client.iter_messages(channel):
            msg_time = message.date.astimezone(KST)

            if msg_time < cutoff:
                break

            if not message.text:
                continue

            link = None
            if message.chat and message.chat.username:
                link = f"https://t.me/{message.chat.username}/{message.id}"

            results.append({
                "source": channel,
                "text": message.text,
                "link": link
            })

    return results