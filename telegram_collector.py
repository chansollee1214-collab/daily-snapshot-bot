from datetime import datetime, timedelta
from config import KST


async def collect_telegram(client, channels):
    cutoff_time = datetime.now(KST) - timedelta(hours=24)

    results = []

    for channel in channels:
        async for message in client.iter_messages(channel):
            msg_time = message.date.astimezone(KST)

            if msg_time < cutoff_time:
                break

            if message.text:
                results.append({
                    "source": channel,
                    "date": msg_time,
                    "text": message.text,
                    "link": f"https://t.me/{message.chat.username}/{message.id}"
                })

    return results