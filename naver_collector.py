import feedparser
from datetime import datetime, timedelta
from config import KST


async def collect_naver(blog_dict):
    results = []
    cutoff = datetime.now(KST) - timedelta(hours=24)

    for blog_id, label in blog_dict.items():
        url = f"https://rss.blog.naver.com/{blog_id}.xml"
        feed = feedparser.parse(url)

        for entry in feed.entries:
            if not hasattr(entry, "published_parsed"):
                continue

            published = datetime(*entry.published_parsed[:6]).astimezone(KST)

            if published < cutoff:
                continue

            results.append({
                "source": blog_id,
                "text": f"{entry.title}\n{entry.summary}",
                "link": entry.link
            })

    return results