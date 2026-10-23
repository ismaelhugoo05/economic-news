"""Build public/ (index, article pages, style.css) from content/articles/*.md."""
import html
import json
import math
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
PUBLIC = ROOT / "public"
SITE_TITLE = "World Economy Watch"
DESK = "Global Desk"

SOURCES = {
    "cnbc.com": "CNBC", "marketwatch.com": "MarketWatch", "federalreserve.gov": "Federal Reserve",
    "finance.yahoo.com": "Yahoo Finance", "worldbank.org": "World Bank",
}

# (label, Yahoo symbol, invert the quote, price format); quotes are a build-time snapshot, not a live feed
MARKETS = [
    ("S&P 500", "^GSPC", False, "{:,.2f}"),
    ("US 10Y", "^TNX", False, "{:.3f}%"),
    ("Crude Oil", "CL=F", False, "${:,.2f}"),
    ("Gold", "GC=F", False, "${:,.2f}"),
    ("USD/EUR", "EURUSD=X", True, "{:.4f}"),
]

# shortcut: first keyword hit (title before summary) picks the section label; upgrade to a classifier if labels look wrong
TOPICS = [
    (name, re.compile(rf"\b({words})\b", re.I))
    for name, words in [
        ("Inflation", r"inflation|inflationary|cpi|ppi|consumer prices"),
        ("Central Banks", r"fed|federal reserve|ecb|central banks?|rate (hike|cut)s?|interest rates?|rates"),
        ("Trade", r"tariffs?|trade|exports?|imports?"),
        ("Fiscal", r"deficit|budget|debt|treasury|imf"),
        ("Labor", r"jobs|payrolls|unemployment|wages|labor"),
        ("Growth", r"gdp|growth|recession|economy|housing"),
        ("Markets", r"yields?|bonds?|stocks?|shares|dollar|currenc(y|ies)|markets?"),
    ]
]

FONTS = (
    "https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600"
    "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap"
)

CSS = """\
:root{color-scheme:light;--paper:#faf7f2;--ink:#111827;--body:#1f2937;--muted:#57534e;--rule:#e5e0d8;--rule-strong:#111827;
--accent:#881337;--up:#166534;--down:#9f1239;
--display:"Playfair Display",Georgia,"Times New Roman",serif;--serif:"Source Serif 4",Georgia,"Times New Roman",serif}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--body);font:1.0625rem/1.65 var(--serif);-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration-thickness:1px;text-underline-offset:.15em}
h1,h2,h3{font-family:var(--display);color:var(--ink);margin:0;line-height:1.15;text-wrap:balance}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.wrap{max-width:74rem;margin:0 auto;padding:0 1.25rem}
.masthead{padding-top:1rem;text-align:center}
.topline{display:flex;flex-wrap:wrap;justify-content:space-between;gap:.25rem 1rem;padding-bottom:.6rem;border-bottom:1px solid var(--rule);
font-size:.75rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.nameplate{display:block;padding:1.1rem 0 .9rem;font:800 clamp(2.1rem,7vw,4.5rem)/1 var(--display);letter-spacing:-.01em;color:var(--ink);text-decoration:none}
.markets{display:flex;flex-wrap:wrap;justify-content:center;gap:.35rem 1.75rem;margin:0;padding:.55rem 0;list-style:none;
border-top:3px double var(--rule-strong);border-bottom:1px solid var(--rule-strong);font-size:.8125rem;font-variant-numeric:tabular-nums;color:var(--muted)}
.markets b{color:var(--ink);font-weight:600;margin:0 .3rem}
.markets .asof{font-style:italic}
.up{color:var(--up)}
.down{color:var(--down)}
.rule-only{border-top:3px double var(--rule-strong);border-bottom:1px solid var(--rule-strong);height:6px}
.label{display:block;margin:0 0 .6rem;font:600 .75rem/1.2 var(--serif);letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.dateline{margin:0;font-size:.8125rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.dateline b{color:var(--ink);font-weight:600}
.story-link{text-decoration:none}
.story-link:hover,.story-link:focus-visible{text-decoration:underline}
.story-link:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
main{padding-bottom:4rem}
.lead{padding:2.5rem 0;border-bottom:1px solid var(--rule-strong);display:grid;gap:1rem}
@media (min-width:64rem){.lead{grid-template-columns:minmax(0,3fr) minmax(0,2fr);column-gap:3rem;align-items:start}}
.lead h2{font-size:clamp(2.1rem,5vw,3.75rem);font-weight:700;letter-spacing:-.015em}
.lead .standfirst{margin:0 0 1rem;font-size:1.25rem;line-height:1.55;color:var(--body)}
@media (min-width:64rem){.lead-side{border-left:1px solid var(--rule);padding-left:3rem}}
.section-head{display:flex;align-items:baseline;gap:1rem;margin:2.25rem 0 0;padding-bottom:.5rem;border-bottom:1px solid var(--rule-strong);
font:700 1.05rem var(--display);color:var(--ink)}
.grid{display:grid;grid-template-columns:1fr;gap:1px;background:var(--rule);margin:0;padding:0;list-style:none;border-bottom:1px solid var(--rule)}
@media (min-width:56rem){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
.item{background:var(--paper);padding:1.5rem 0;display:flex;flex-direction:column;gap:.55rem}
@media (min-width:56rem){.item{padding:1.5rem 1.75rem}.item:nth-child(3n+1){padding-left:0}.item:nth-child(3n){padding-right:0}}
.item h3{font-size:1.35rem;font-weight:700}
.item p{margin:0}
.item .dateline{margin-top:auto;padding-top:.25rem}
.article{max-width:42rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
.crumbs{margin:0 0 1.5rem;font-size:.8125rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.crumbs a{text-decoration:none}
.crumbs a:hover{text-decoration:underline}
.article header{padding-bottom:1.5rem;margin-bottom:2rem;border-bottom:1px solid var(--rule-strong);display:grid;gap:1rem}
.article h1{font-size:clamp(2.1rem,5vw,3.25rem);font-weight:700;letter-spacing:-.015em}
.source-link{font-size:.9375rem;font-style:italic;color:var(--accent)}
.prose{font-size:1.1875rem;line-height:1.75}
.prose > p:first-child::first-letter{float:left;font:700 3.6em/.82 var(--display);margin:.06em .1em 0 0;color:var(--ink)}
.prose h2,.prose h3{margin:2.25rem 0 .75rem;padding-top:.75rem;border-top:1px solid var(--rule);font-size:1.4rem}
.prose p,.prose ul{margin:0 0 1.25rem}
.prose ul{padding-left:1.25rem}
.prose li{margin:.5rem 0}
.prose li::marker{color:var(--accent)}
.prose strong{color:var(--ink)}
.prose a{color:var(--accent)}
.colophon{border-top:1px solid var(--rule-strong);padding:1.25rem 0 2.5rem;font-size:.8125rem;color:var(--muted);text-align:center}
"""


def parse_article(text):
    _, front, body = text.split("---\n", 2)
    meta = {}
    for line in front.splitlines():
        key, _, value = line.partition(": ")
        try:
            meta[key] = json.loads(value)  # fetch_news.py writes values as JSON strings
        except ValueError:
            meta[key] = value
    return meta, body


def inline(text):
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\*(\S.*?)\*", r"<em>\1</em>", text)


def markdown(body):
    # shortcut: headings, "- " lists, bold, links and paragraphs only; swap in a real parser if articles need more
    out, para, items = [], [], []

    def flush():
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>")
            items.clear()

    for line in body.splitlines():
        line = line.strip()
        if m := re.match(r"(#{1,6}) +(.*)", line):
            flush()
            out.append(f"<h{len(m[1])}>{inline(m[2])}</h{len(m[1])}>")
        elif line[:2] in ("- ", "* "):
            if para:
                flush()
            items.append(line[2:])
        elif line:
            if items:
                flush()
            para.append(line)
        else:
            flush()
    flush()
    return "\n".join(out)


def sentences(text, n):
    # shortcut: splits after ., ! or ? that follows a lowercase letter, digit, % or ), so "U.S." stays whole
    parts = re.split(r"(?<=[a-z0-9%)][.!?])\s+(?=[A-Z\"“'‘])", text.strip())
    return " ".join(parts[:n])


def topic_of(title, summary):
    for text in (title, summary):
        for name, pattern in TOPICS:
            if pattern.search(text):
                return name
    return "Economy"


def source_name(url):
    host = urlparse(url).netloc.removeprefix("www.")
    return SOURCES.get(host, host)


def read_minutes(body):
    return max(1, math.ceil(len(body.split()) / 230))


def parse_date(date):
    try:
        d = datetime.fromisoformat(date)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def long_date(d):
    return f"{d:%B} {d.day}, {d.year}"


def dateline(s):
    d = parse_date(s["date"])
    when = f'<time datetime="{html.escape(s["date"])}">{long_date(d) if d else html.escape(s["date"][:10])}</time>'
    return f'<p class="dateline"><b>{DESK}</b> — {when} · {s["minutes"]} min read</p>'


def quote(chart, invert=False):
    """(price, % change vs previous close) from a Yahoo chart response."""
    closes = [c for c in chart["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c is not None]
    price, prev = closes[-1], closes[-2]
    if invert:
        price, prev = 1 / price, 1 / prev
    return price, (price - prev) / prev * 100


def market_quotes():
    quotes = []
    for label, symbol, invert, fmt in MARKETS:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5d&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (econ-news-pipeline)"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                price, change = quote(json.load(r), invert)
        except (OSError, ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as e:
            print(f"no quote for {label}: {e}", file=sys.stderr)  # the markets line just leaves that benchmark out
            continue
        quotes.append((label, fmt.format(price), change))
    return quotes


def markets_line(quotes, synced):
    if not quotes:
        return '<div class="rule-only"></div>'
    items = "".join(
        f'<li>{label}<b>{px}</b><span class="{"up" if chg >= 0 else "down"}">{"▲" if chg >= 0 else "▼"} {abs(chg):.2f}%</span></li>'
        for label, px, chg in quotes
    )
    return f'<ul class="markets" aria-label="Markets">{items}<li class="asof">Markets as of {synced}</li></ul>'


def masthead(root, quotes, built):
    synced = f"{built:%H:%M} UTC"
    return f"""<header class="masthead wrap">
<div class="topline"><span>Global Edition</span><span>{built:%A}, {long_date(built)}</span><span>Published daily</span></div>
<a class="nameplate" href="{root}index.html">{SITE_TITLE}</a>
{markets_line(quotes, synced)}
</header>"""


def page(title, content, root, header):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
{header}
{content}
<footer class="colophon wrap">{SITE_TITLE} · Reports are synthesized from the primary sources credited in each article.</footer>
</body>
</html>
"""


def lead_story(s):
    return (
        f'<article class="lead"><div><span class="label">{s["topic"]}</span>'
        f'<h2><a class="story-link" href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></h2></div>'
        f'<div class="lead-side"><p class="standfirst">{html.escape(sentences(s["summary"], 2))}</p>{dateline(s)}</div></article>'
    )


def grid_item(s):
    return (
        f'<li class="item"><span class="label">{s["topic"]}</span>'
        f'<h3><a class="story-link" href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></h3>'
        f'<p>{html.escape(sentences(s["summary"], 1))}</p>{dateline(s)}</li>'
    )


def article_page(s):
    url = s["url"]
    source = (
        f'<a class="source-link" href="{html.escape(url)}" target="_blank" rel="noopener">Primary source: {html.escape(s["source"])} &#8599;</a>'
        if url.startswith(("https://", "http://")) else ""
    )
    return (
        f'<main class="article"><article>\n<p class="crumbs"><a href="../index.html">{SITE_TITLE}</a> / {s["topic"]}</p>\n'
        f'<header><span class="label">{s["topic"]}</span>\n<h1>{html.escape(s["title"])}</h1>\n{dateline(s)}\n{source}\n</header>\n'
        f'<div class="prose">\n{s["body"]}\n</div>\n</article></main>'
    )


def main():
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)  # generated output; a clean rebuild drops pages of deleted articles
    (PUBLIC / "articles").mkdir(parents=True)
    (PUBLIC / "style.css").write_text(CSS, encoding="utf-8")

    built = datetime.now(timezone.utc)
    quotes = market_quotes()
    stories = []
    for path in ARTICLES.glob("*.md"):
        meta, body = parse_article(path.read_text(encoding="utf-8"))
        title, summary, url = meta.get("title", path.stem), meta.get("summary", ""), meta.get("source_url", "")
        stories.append({
            "slug": path.stem, "title": title, "summary": summary, "date": meta.get("date", ""),
            "url": url, "source": source_name(url), "topic": topic_of(title, summary), "minutes": read_minutes(body),
            "body": markdown(body),
        })
    stories.sort(key=lambda s: s["date"], reverse=True)

    for s in stories:
        header = masthead("../", quotes, built)
        (PUBLIC / "articles" / f"{s['slug']}.html").write_text(page(s["title"], article_page(s), "../", header), encoding="utf-8")

    if stories:
        # the newest story leads; the front page shows 10, older articles keep their pages
        lead, rest = stories[0], stories[1:10]
        content = (
            f'<main class="wrap"><h1 class="sr-only">{SITE_TITLE}</h1>\n{lead_story(lead)}\n'
            f'<section aria-labelledby="latest"><h2 class="section-head" id="latest">Latest Reports</h2>'
            f'<ul class="grid">' + "".join(grid_item(s) for s in rest) + "</ul></section>\n</main>"
        )
    else:
        content = '<main class="wrap"><p>No stories yet.</p></main>'
    (PUBLIC / "index.html").write_text(page(SITE_TITLE, content, "", masthead("", quotes, built)), encoding="utf-8")
    print(f"built {len(stories)} articles into {PUBLIC.relative_to(ROOT)}/ ({len(quotes)} market quotes)")


if __name__ == "__main__":
    main()
