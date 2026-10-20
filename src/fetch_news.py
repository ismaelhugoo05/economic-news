"""Fetch fresh macroeconomic stories from financial RSS feeds and have Claude write an original
report for each into content/articles/ as Markdown, following the economic-writer skill."""
import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
SEEN = ROOT / "data" / "seen_urls.txt"
WRITER_SKILL = ROOT / ".claude" / "skills" / "economic-writer" / "SKILL.md"
LIMIT = 10
MODEL = "claude-opus-5-5"
OUTPUT_FORMAT = """

## Output format
Reply with the finished report only, in Markdown, nothing before or after it:
- First line: `# <your headline>`
- Then the lead paragraph (plain text, no heading).
- Then `## Macro Context` and `## Key Takeaways` (bullet list of figures).
Do not add a source or attribution line; the pipeline appends the editorial note."""

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


class _Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.depth += 1
            self.parts.append("")

    def handle_endtag(self, tag):
        if tag == "p" and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts[-1] += data


def article_text(page_html):
    parser = _Paragraphs()
    parser.feed(page_html)
    paragraphs = (" ".join(p.split()) for p in parser.parts)
    return "\n\n".join(p for p in paragraphs if len(p) > 40)  # drops captions, bylines, nav snippets


def source_material(s):
    try:
        text = article_text(fetch(s["url"]).decode("utf-8", "replace"))
    except OSError as e:
        print(f"  no page text for {s['url']}: {e}", file=sys.stderr)
        text = ""
    # shortcut: page text capped at 15k chars to bound cost; raise it if reports miss figures from long pieces
    return f"Headline: {s['title']}\nTeaser: {s['summary']}\n\n{text[:15000]}"


def writer_prompt():
    return WRITER_SKILL.read_text(encoding="utf-8").split("---", 2)[2].strip() + OUTPUT_FORMAT


def parse_report(text):
    first, _, body = text.strip().partition("\n")
    if not first.startswith("# "):
        raise ValueError("report has no '# ' headline")
    body = body.strip()
    lead = next((p for p in body.split("\n\n") if not p.startswith(("#", "-", "*"))), "")
    if not lead:
        raise ValueError("report has no lead paragraph")
    return first[2:].strip(), lead, body


def synthesize(client, s):
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # a declined request is retried on a fallback model inside the same call
        output_config={"effort": "medium"},
        system=writer_prompt(),
        messages=[{
            "role": "user",
            "content": f"Source material. Use it for facts only, never for wording.\n\n<source>\n{source_material(s)}\n</source>",
        }],
    )
    if response.stop_reason != "end_turn":
        raise ValueError(f"model stopped with {response.stop_reason}")
    return parse_report("".join(b.text for b in response.content if b.type == "text"))


def to_markdown(s, headline, lead, body):
    # JSON strings are valid YAML double-quoted scalars, so quotes/colons in titles are safe
    return (
        "---\n"
        f"title: {json.dumps(headline, ensure_ascii=False)}\n"
        f"date: {s['date'].isoformat()}\n"
        f"source_url: {json.dumps(s['url'])}\n"
        f"summary: {json.dumps(lead, ensure_ascii=False)}\n"
        "---\n\n"
        f"{body}\n\nReporting synthesized from [{s['source']}]({s['url']}) primary disclosures.\n"
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

    client = anthropic.Anthropic()
    written = 0
    with SEEN.open("a", encoding="utf-8") as seen_file:
        for s in sorted(fresh.values(), key=lambda s: s["date"], reverse=True):
            if written == LIMIT:
                break
            try:
                headline, lead, body = synthesize(client, s)
            except (anthropic.AuthenticationError, TypeError) as e:  # the SDK raises TypeError when no credentials exist
                raise SystemExit(f"Claude API authentication failed: {e}")
            except (anthropic.APIError, ValueError) as e:
                print(f"skipped {s['url']}: {e}", file=sys.stderr)  # not marked seen, so the next run retries it
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", headline.lower()).strip("-")[:60]
            path = ARTICLES / f"{s['date']:%Y-%m-%d}-{slug}-{hashlib.sha1(s['url'].encode()).hexdigest()[:6]}.md"
            path.write_text(to_markdown(s, headline, lead, body), encoding="utf-8")
            seen_file.write(s["url"] + "\n")  # only after the file is written, so a crash never loses a story
            seen_file.flush()
            written += 1
            print(f"{path.relative_to(ROOT)} ({len(body.split())} words)")
    print(f"{written} new stories")


if __name__ == "__main__":
    main()
