"""Build public/ (index, article pages, style.css, app.js) from content/articles/*.md."""
import html
import json
import math
import re
import shutil
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
PUBLIC = ROOT / "public"
APP_JS = Path(__file__).with_name("app.js")
SITE_TITLE = "Economic News"
CHART_DAYS = 14

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

# shortcut: first keyword hit (title before summary) picks the badge; upgrade to a classifier if badges look wrong
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

FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"

# applied before first paint so a saved dark choice never flashes light
THEME_BOOT = '<script>try{if(localStorage.getItem("theme")==="dark")document.documentElement.dataset.theme="dark"}catch(e){}</script>'

CSS = """\
:root{color-scheme:light;--bg:#f4f5f7;--card:#fff;--text:#1e293b;--head:#0f172a;--muted:#5b6678;--line:#e2e8f0;
--accent:#1d4ed8;--badge-bg:#eef2ff;--badge:#3730a3;--up:#047857;--down:#b91c1c;
--c1:#1d4ed8;--c2:#b45309;--c3:#047857;--c4:#b91c1c;--shadow:0 1px 2px rgb(15 23 42/.05),0 8px 24px -12px rgb(15 23 42/.12);
--sans:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0b0f19;--card:#151d2e;--text:#cbd5e1;--head:#f1f5f9;--muted:#94a3b8;--line:#26324a;
--accent:#e0a84f;--badge-bg:#2a2418;--badge:#e0a84f;--up:#34d399;--down:#f87171;
--c1:#7aa2f7;--c2:#e0a84f;--c3:#34d399;--c4:#f87171;--shadow:0 1px 2px rgb(0 0 0/.3)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:1rem/1.65 var(--sans);-webkit-font-smoothing:antialiased;transition:background-color .3s,color .3s}
a{color:var(--accent);text-underline-offset:.15em}
h1,h2,h3{color:var(--head);margin:0;line-height:1.25;letter-spacing:-.015em;text-wrap:balance}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.wrap{max-width:76rem;margin:0 auto;padding:0 1.25rem}
.masthead{background:var(--card);border-bottom:1px solid var(--line);transition:background-color .3s,border-color .3s}
.bar{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding-block:1rem}
.brand{color:var(--head);text-decoration:none;font-weight:700;font-size:1.25rem;letter-spacing:-.02em}
.bar-end{display:flex;align-items:center;gap:1rem;color:var(--muted);font-size:.8125rem}
.theme-toggle{font:500 .8125rem var(--sans);color:var(--text);background:transparent;border:1px solid var(--line);border-radius:999px;padding:.35rem .8rem;cursor:pointer;transition:border-color .2s,background-color .2s}
.theme-toggle:hover{border-color:var(--muted)}
.theme-toggle:focus-visible,.story-link:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.ticker{border-top:1px solid var(--line);font-size:.8125rem;overflow-x:auto;scrollbar-width:none}
.ticker::-webkit-scrollbar{display:none}
.ticker ul{display:flex;gap:1.75rem;margin:0;padding:.5rem 0;list-style:none;white-space:nowrap;font-variant-numeric:tabular-nums}
.ticker .asof{color:var(--muted)}
.sym{color:var(--muted);margin-right:.4rem}
.px{color:var(--head);font-weight:500;margin-right:.35rem}
.up{color:var(--up)}
.down{color:var(--down)}
.layout{display:grid;gap:2.5rem;padding-block:2.5rem 4rem}
@media (min-width:64rem){.layout{grid-template-columns:minmax(0,1fr) 19rem;align-items:start}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);transition:background-color .3s,border-color .3s}
.lead{position:relative;padding:clamp(1.75rem,4vw,3rem);display:flex;flex-direction:column;gap:1rem}
.lead h2{font-size:clamp(1.75rem,3.5vw,2.6rem)}
.lead .summary{font-size:1.125rem;max-width:62ch;margin:0}
.kicker{display:flex;flex-wrap:wrap;align-items:center;gap:.6rem;margin:0;font-size:.75rem;color:var(--muted)}
.badge{font-weight:600;color:var(--badge);background:var(--badge-bg);border-radius:999px;padding:.2rem .6rem}
.meta{margin:0;font-size:.8125rem;color:var(--muted)}
.story-link{color:inherit;text-decoration:none}
.story-link::after{content:"";position:absolute;inset:0}
.lead:hover h2,.story:hover h3{color:var(--accent)}
.section-title{font-size:.8125rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:2.75rem 0 0}
.stories{display:grid;column-gap:2.5rem;margin:0;padding:0;list-style:none}
@media (min-width:44rem){.stories{grid-template-columns:repeat(2,minmax(0,1fr))}}
.story{position:relative;display:flex;flex-direction:column;gap:.5rem;padding:1.5rem 0;border-bottom:1px solid var(--line)}
.story h3{font-size:1.125rem;transition:color .2s}
.story .summary{margin:0;font-size:.9375rem}
.side{display:grid;gap:1.25rem}
@media (min-width:64rem){.side{position:sticky;top:1.5rem}}
.widget{padding:1.25rem}
.widget h2{font-size:.9375rem;margin-bottom:.25rem}
.widget .meta{margin-bottom:.75rem}
.chart-wrap{position:relative}
#coverage-chart{display:block;width:100%;height:170px}
.legend{display:flex;flex-wrap:wrap;gap:.25rem .9rem;margin:.75rem 0 0;padding:0;list-style:none;font-size:.75rem;color:var(--muted)}
.legend li::before{content:"";display:inline-block;width:.6rem;height:.6rem;margin-right:.35rem;border-radius:2px;background:var(--c);vertical-align:-.05em}
.chart-tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);padding:.45rem .65rem;font-size:.75rem;line-height:1.5;color:var(--text);white-space:nowrap}
.article{max-width:720px;margin:0 auto;padding:2.5rem 1.25rem 4rem}
.crumbs{display:flex;gap:.5rem;font-size:.8125rem;color:var(--muted);margin-bottom:1.5rem}
.crumbs a{text-decoration:none}
.article header{display:flex;flex-direction:column;gap:1rem;padding-bottom:2rem;margin-bottom:2rem;border-bottom:1px solid var(--line)}
.article h1{font-size:clamp(1.9rem,4.5vw,2.75rem)}
.prose{font-size:1.0625rem;line-height:1.8}
.prose h2,.prose h3{margin:2.25rem 0 .75rem;font-size:1.3rem}
.prose p,.prose ul{margin:0 0 1.25rem}
.prose ul{padding-left:1.25rem}
.prose li{margin:.5rem 0}
.prose strong{color:var(--head)}
.button{align-self:flex-start;font-weight:600;font-size:.875rem;color:var(--card);background:var(--head);border-radius:8px;padding:.65rem 1.1rem;text-decoration:none;transition:opacity .2s}
.button:hover,.button:focus-visible{opacity:.85;color:var(--card)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
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


def time_tag(date):
    d = parse_date(date)
    label = f"{d:%b} {d.day}, {d.year}" if d else date[:10]
    return f'<time datetime="{html.escape(date)}">{html.escape(label)}</time>'


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
            print(f"no quote for {label}: {e}", file=sys.stderr)  # the ticker just leaves that benchmark out
            continue
        quotes.append((label, fmt.format(price), change))
    return quotes


def coverage_series(stories, today, days=CHART_DAYS, top=4):
    """Stories per day for the most-covered topics over the last `days` days."""
    start = today - timedelta(days=days - 1)
    window = [s for s in stories if s["dt"] and start <= s["dt"].date() <= today]
    names = [name for name, _ in Counter(s["topic"] for s in window).most_common(top)]
    labels = [start + timedelta(days=i) for i in range(days)]
    counts = Counter((s["topic"], s["dt"].date()) for s in window)
    return {
        "days": [f"{d:%b} {d.day}" for d in labels],
        "series": [{"name": n, "values": [counts[(n, d)] for d in labels]} for n in names],
    }


def ticker(quotes, synced):
    if not quotes:
        return ""
    items = "".join(
        f'<li><span class="sym">{label}</span><span class="px">{px}</span>'
        f'<span class="{"up" if chg >= 0 else "down"}">{"▲" if chg >= 0 else "▼"} {abs(chg):.2f}%</span></li>'
        for label, px, chg in quotes
    )
    return (
        f'<div class="ticker" role="region" aria-label="Market snapshot"><div class="wrap">'
        f'<ul>{items}<li class="asof">as of {synced}</li></ul></div></div>'
    )


def masthead(root, quotes, built):
    synced = f"{built:%b} {built.day}, {built:%H:%M} UTC"
    return f"""<header class="masthead">
<div class="wrap bar">
<a class="brand" href="{root}index.html">{SITE_TITLE}</a>
<div class="bar-end"><span>Updated {built:%b} {built.day}, {built.year}</span>
<button class="theme-toggle" type="button" hidden>&#9790; Dark</button></div>
</div>
{ticker(quotes, synced)}
</header>"""


def page(title, content, root, header):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
{THEME_BOOT}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{root}style.css">
<script src="{root}app.js" defer></script>
</head>
<body>
{header}
{content}
</body>
</html>
"""


def kicker(s):
    return f'<p class="kicker"><span class="badge">{s["topic"]}</span><span>{html.escape(s["source"])}</span></p>'


def lead_card(s):
    return (
        f'<article class="card lead">{kicker(s)}'
        f'<h2><a class="story-link" href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></h2>'
        f'<p class="summary">{html.escape(sentences(s["summary"], 2))}</p>'
        f'<p class="meta">{time_tag(s["date"])} · {s["minutes"]} min read</p></article>'
    )


def story_item(s):
    return (
        f'<li class="story">{kicker(s)}'
        f'<h3><a class="story-link" href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></h3>'
        f'<p class="summary">{html.escape(sentences(s["summary"], 1))}</p>'
        f'<p class="meta">{time_tag(s["date"])} · {s["minutes"]} min read</p></li>'
    )


def chart_card(series):
    legend = "".join(f'<li style="--c:var(--c{i})">{html.escape(s["name"])}</li>' for i, s in enumerate(series["series"], 1))
    totals = ", ".join(f'{s["name"]} {sum(s["values"])}' for s in series["series"]) or "no stories"
    data = json.dumps(series).replace("</", "<\\/")
    return (
        f'<section class="card widget" aria-labelledby="chart-title"><h2 id="chart-title">Coverage by topic</h2>'
        f'<p class="meta">Stories per day, last {CHART_DAYS} days</p>'
        f'<div class="chart-wrap"><canvas id="coverage-chart" role="img" aria-label="Stories per topic over the last {CHART_DAYS} days: {totals}"></canvas>'
        f'<div class="chart-tip" id="chart-tip" hidden></div></div><ul class="legend">{legend}</ul>'
        f'<script type="application/json" id="coverage-data">{data}</script></section>'
    )


def article_page(s):
    url = s["url"]
    button = (
        f'<a class="button" href="{html.escape(url)}" target="_blank" rel="noopener">Read primary source &#8599;</a>'
        if url.startswith(("https://", "http://")) else ""
    )
    return (
        f'<main class="article"><article>\n<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Home</a>'
        f'<span aria-hidden="true">/</span><span aria-current="page">{s["topic"]}</span></nav>\n'
        f'<header>{kicker(s)}\n<h1>{html.escape(s["title"])}</h1>\n'
        f'<p class="meta">{time_tag(s["date"])} · {s["minutes"]} min read</p>\n{button}\n</header>\n'
        f'<div class="prose">\n{s["body"]}\n</div>\n</article></main>'
    )


def main():
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)  # generated output; a clean rebuild drops pages of deleted articles
    (PUBLIC / "articles").mkdir(parents=True)
    (PUBLIC / "style.css").write_text(CSS, encoding="utf-8")
    shutil.copyfile(APP_JS, PUBLIC / "app.js")

    built = datetime.now(timezone.utc)
    quotes = market_quotes()
    stories = []
    for path in ARTICLES.glob("*.md"):
        meta, body = parse_article(path.read_text(encoding="utf-8"))
        title, summary, url = meta.get("title", path.stem), meta.get("summary", ""), meta.get("source_url", "")
        stories.append({
            "slug": path.stem, "title": title, "summary": summary, "date": meta.get("date", ""), "dt": parse_date(meta.get("date", "")),
            "url": url, "source": source_name(url), "topic": topic_of(title, summary), "minutes": read_minutes(body),
            "body": markdown(body),
        })
    stories.sort(key=lambda s: s["date"], reverse=True)

    for s in stories:
        header = masthead("../", quotes, built)
        (PUBLIC / "articles" / f"{s['slug']}.html").write_text(page(s["title"], article_page(s), "../", header), encoding="utf-8")

    if stories:
        # the newest story leads; the home page shows 10, older articles keep their pages
        lead, rest = stories[0], stories[1:10]
        content = (
            f'<main class="wrap layout"><h1 class="sr-only">{SITE_TITLE}</h1>\n<div>'
            f'<section aria-label="Lead story">{lead_card(lead)}</section>\n'
            f'<section aria-labelledby="latest"><h2 class="section-title" id="latest">Latest</h2>'
            f'<ul class="stories">' + "".join(story_item(s) for s in rest) + "</ul></section></div>\n"
            f'<aside class="side">{chart_card(coverage_series(stories, built.date()))}</aside>\n</main>'
        )
    else:
        content = '<main class="wrap layout"><p>No stories yet.</p></main>'
    (PUBLIC / "index.html").write_text(page(SITE_TITLE, content, "", masthead("", quotes, built)), encoding="utf-8")
    print(f"built {len(stories)} articles into {PUBLIC.relative_to(ROOT)}/ ({len(quotes)} market quotes)")


if __name__ == "__main__":
    main()
