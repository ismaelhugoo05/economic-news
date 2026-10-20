"""Fetch fresh macroeconomic stories from financial RSS feeds into content/articles/ as Markdown."""
import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
SEEN = ROOT / "data" / "seen_urls.txt"
LIMIT = 10

# AP has no public RSS feed, so it is not listed.
FEEDS = {
    "CNBC Finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "CNBC Economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}

# shortcut: keyword match on title+summary, upgrade to a classifier if too many false hits
MACRO = re.compile(
    r"\b(gdp|inflation|cpi|ppi|interest rates?|rate (cut|hike)s?|fed|federal reserve|ecb|central banks?"
    r"|treasur(y|ies)|bond yields?|yields|jobs report|payrolls|unemployment|recession|tariffs?|trade war"
    r"|economy|economic|deficit|currenc(y|ies)|dollar)\b",
    re.I,
)


def clean(text):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def parse(xml_bytes, source):
    # shortcut: RSS 2.0 <item> only, add Atom <entry> if a feed needs it
    for item in ET.fromstring(xml_bytes).iter("item"):
        title = clean(item.findtext("title") or "")
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue
        try:
            date = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
        except (TypeError, ValueError):
            date = datetime.now(timezone.utc)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        yield {"title": title, "url": url, "date": date, "summary": clean(item.findtext("description") or ""), "source": source}


def is_macro(story):
    return bool(MACRO.search(f"{story['title']} {story['summary']}"))


def to_markdown(s):
    # JSON strings are valid YAML double-quoted scalars, so quotes/colons in titles are safe
    return (
        "---\n"
        f"title: {json.dumps(s['title'], ensure_ascii=False)}\n"
        f"date: {s['date'].isoformat()}\n"
        f"source_url: {json.dumps(s['url'])}\n"
        f"summary: {json.dumps(s['summary'], ensure_ascii=False)}\n"
        "---\n\n"
        f"{s['summary']}\n\nSource: [{s['source']}]({s['url']})\n"
    )


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (econ-news-pipeline)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def main():
    ARTICLES.mkdir(parents=True, exist_ok=True)
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    seen = set(SEEN.read_text(encoding="utf-8").split()) if SEEN.exists() else set()

    fresh = {}
    for source, feed in FEEDS.items():
        try:
            items = list(parse(fetch(feed), source))
        except (OSError, ET.ParseError) as e:
            print(f"skipped {source}: {e}", file=sys.stderr)
            continue
        for s in items:
            if s["url"] not in seen and is_macro(s):
                fresh.setdefault(s["url"], s)

    top = sorted(fresh.values(), key=lambda s: s["date"], reverse=True)[:LIMIT]
    with SEEN.open("a", encoding="utf-8") as seen_file:
        for s in top:
            slug = re.sub(r"[^a-z0-9]+", "-", s["title"].lower()).strip("-")[:60]
            path = ARTICLES / f"{s['date']:%Y-%m-%d}-{slug}-{hashlib.sha1(s['url'].encode()).hexdigest()[:6]}.md"
            path.write_text(to_markdown(s), encoding="utf-8")
            seen_file.write(s["url"] + "\n")  # only after the file is written, so a crash never loses a story
            print(path.relative_to(ROOT))
    print(f"{len(top)} new stories")


if __name__ == "__main__":
    main()
