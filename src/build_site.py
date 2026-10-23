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

from fetch_news import FEEDS

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
PUBLIC = ROOT / "public"
APP_JS = Path(__file__).with_name("app.js")
SITE_TITLE = "Economic News"
CHART_DAYS = 14
NEW_HOURS = 36

SOURCES = {
    "cnbc.com": "CNBC", "marketwatch.com": "MarketWatch", "federalreserve.gov": "Federal Reserve",
    "finance.yahoo.com": "Yahoo Finance", "worldbank.org": "World Bank",
}

# (label, Yahoo symbol, invert the quote, price format); quotes are a build-time snapshot, not a live feed
MARKETS = [
    ("USD/EUR", "EURUSD=X", True, "{:.4f}"),
    ("S&P 500", "^GSPC", False, "{:,.2f}"),
    ("CRUDE OIL", "CL=F", False, "${:,.2f}"),
    ("GOLD", "GC=F", False, "${:,.2f}"),
    ("US 10Y YIELD", "^TNX", False, "{:.3f}%"),
    ("BTC/USD", "BTC-USD", False, "${:,.0f}"),
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

FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Share+Tech+Mono&display=swap"

CSS = """\
:root{color-scheme:dark;--bg:#070a13;--panel:#0b1120;--panel-hi:#0f1830;--line:#1b2a44;--fg:#e6edf7;--body:#c3cede;--muted:#8a98ae;
--blue:#00f0ff;--amber:#ffb703;--red:#ff003c;--green:#00ff9c;
--mono:"Share Tech Mono",ui-monospace,"Cascadia Mono",Consolas,monospace;--sans:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
*{box-sizing:border-box}
body{margin:0;background-color:var(--bg);color:var(--body);font:1rem/1.6 var(--sans);-webkit-font-smoothing:antialiased;
background-image:linear-gradient(color-mix(in srgb,var(--blue) 5%,transparent) 1px,transparent 1px),linear-gradient(90deg,color-mix(in srgb,var(--blue) 5%,transparent) 1px,transparent 1px);
background-size:48px 48px}
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:10;
background:repeating-linear-gradient(to bottom,color-mix(in srgb,var(--fg) 3%,transparent) 0 1px,transparent 1px 3px)}
a{color:var(--blue);text-underline-offset:.15em}
h1,h2,h3{color:var(--fg);margin:0;line-height:1.25;text-wrap:balance}
.mono,.status,.ticker,.badge,.src,.flag,.meta,.panel-title,.log,.brand,.crumbs{font-family:var(--mono);letter-spacing:.04em}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.wrap{max-width:84rem;margin:0 auto;padding:0 1rem}
.masthead{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
.bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.5rem 1.5rem;padding-block:.85rem}
.brand{color:var(--fg);text-decoration:none;font-size:1.35rem;text-transform:uppercase}
.brand b{color:var(--blue);font-weight:400}
.cursor{color:var(--blue);animation:blink 1s steps(1) infinite}
.status{margin:0;display:flex;flex-wrap:wrap;gap:.25rem 1rem;font-size:.75rem;color:var(--muted);text-transform:uppercase}
.status b{color:var(--green);font-weight:400}
.dot{display:inline-block;width:.5rem;height:.5rem;margin-right:.35rem;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 1.6s ease-in-out infinite}
.ticker{overflow:hidden;border-top:1px solid var(--line);font-size:.8125rem;white-space:nowrap}
.ticker-rail{display:flex;width:max-content;animation:marquee 45s linear infinite}
.ticker:hover .ticker-rail{animation-play-state:paused}
.ticker ul{display:flex;margin:0;padding:0;list-style:none}
.ticker li{padding:.45rem 1.5rem;border-right:1px solid var(--line)}
.ticker .asof{color:var(--amber)}
.sym{color:var(--fg)}
.px{color:var(--body);margin-inline:.5rem}
.up{color:var(--green)}
.down{color:var(--red)}
.up i,.down i{font-style:normal;display:inline-block;animation:nudge 1.4s ease-in-out infinite}
.down i{animation-direction:reverse}
.hud{display:grid;gap:1.25rem;padding-block:1.5rem 4rem}
@media (min-width:64rem){.hud{grid-template-columns:minmax(0,1fr) 22rem;align-items:start}}
.primary{display:grid;gap:1.25rem;min-width:0}
.panel{position:relative;background:color-mix(in srgb,var(--panel) 92%,transparent);border:1px solid var(--line);padding:1rem}
.panel::before,.panel::after{content:"";position:absolute;width:12px;height:12px;border:2px solid var(--blue);pointer-events:none}
.panel::before{top:-1px;left:-1px;border-right:0;border-bottom:0}
.panel::after{bottom:-1px;right:-1px;border-left:0;border-top:0}
.panel-title{display:flex;justify-content:space-between;gap:1rem;margin:0 0 .75rem;font-size:.75rem;font-weight:400;color:var(--muted);text-transform:uppercase}
.panel-title b{color:var(--blue);font-weight:400}
.chart-wrap{position:relative}
#coverage-chart{display:block;width:100%;height:260px;cursor:crosshair}
.legend{display:flex;flex-wrap:wrap;gap:.25rem 1rem;margin:.75rem 0 0;padding:0;list-style:none;font:.75rem var(--mono)}
.legend li::before{content:"";display:inline-block;width:.75rem;height:2px;margin-right:.4rem;vertical-align:middle;background:var(--c);box-shadow:0 0 6px var(--c)}
.chart-tip{position:absolute;pointer-events:none;background:var(--panel-hi);border:1px solid var(--blue);padding:.4rem .6rem;font:.75rem/1.5 var(--mono);color:var(--fg);box-shadow:0 0 16px color-mix(in srgb,var(--blue) 30%,transparent);white-space:nowrap}
.briefs{display:grid;gap:1.25rem}
@media (min-width:40rem){.briefs{grid-template-columns:repeat(2,minmax(0,1fr))}}
.brief{display:flex;flex-direction:column;gap:.6rem;transition:border-color .2s,box-shadow .2s,transform .2s}
.brief:hover,.brief:focus-within{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue),0 0 24px color-mix(in srgb,var(--blue) 25%,transparent);transform:translateY(-2px)}
.brief-head{display:flex;flex-wrap:wrap;align-items:center;gap:.6rem;margin:0}
.badge{font-size:.7rem;text-transform:uppercase;color:var(--amber);border:1px solid color-mix(in srgb,var(--amber) 60%,transparent);padding:.1rem .45rem}
.src{font-size:.7rem;color:var(--muted);text-transform:uppercase}
.flag{margin-left:auto;font-size:.7rem;color:var(--red);animation:pulse 1.6s ease-in-out infinite}
.brief h2,.brief h3{font-family:var(--sans);font-weight:700}
.brief h3{font-size:1.05rem}
.brief a{color:var(--fg);text-decoration:none}
.brief a::after{content:"";position:absolute;inset:0}
.brief:hover h2 a,.brief:hover h3 a,.brief a:focus-visible{color:var(--blue)}
.brief a:focus-visible{outline:none}
.summary{margin:0;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
.meta{margin:0;margin-top:auto;font-size:.72rem;color:var(--muted);text-transform:uppercase}
.lead{border-color:color-mix(in srgb,var(--blue) 45%,var(--line));padding:1.5rem}
.lead h2{font-size:clamp(1.5rem,3vw,2.25rem)}
.lead .summary{-webkit-line-clamp:5;font-size:1.05rem}
.sidebar{display:grid;gap:1.25rem;min-width:0}
@media (min-width:64rem){.sidebar{position:sticky;top:7.5rem}}
.log{margin:0;padding:0;list-style:none;font-size:.8rem;max-height:28rem;overflow:auto}
.log li{padding:.45rem 0;border-bottom:1px dashed var(--line);opacity:0;animation:cascade .4s ease-out forwards;animation-delay:calc(var(--i) * 120ms)}
.log time{color:var(--green)}
.log .lvl{color:var(--amber)}
.log a{color:var(--body);text-decoration:none}
.log a:hover{color:var(--blue)}
.log .prompt{color:var(--blue);border:0}
.points{margin:0;padding-left:1.1rem;font-size:.9rem}
.points li{margin:.5rem 0}
.points li::marker{color:var(--blue)}
.story{max-width:720px;margin:0 auto;padding:2rem 1rem 4rem}
.crumbs{display:flex;gap:.5rem;font-size:.75rem;color:var(--muted);text-transform:uppercase;margin-bottom:1.25rem}
.crumbs a{text-decoration:none}
.story header{display:flex;flex-direction:column;gap:1rem;padding-bottom:1.75rem;margin-bottom:2rem;border-bottom:1px solid var(--line)}
.story h1{font-size:clamp(1.85rem,4.5vw,2.6rem);font-weight:700}
.story .meta{margin:0}
.prose{font-size:1.0625rem;line-height:1.8}
.prose h2,.prose h3{margin:2.25rem 0 .75rem;font:400 1.15rem var(--mono);color:var(--blue);text-transform:uppercase;letter-spacing:.06em}
.prose h2::before{content:"// ";color:var(--muted)}
.prose p,.prose ul{margin:0 0 1.25rem}
.prose ul{padding-left:1.25rem}
.prose li{margin:.5rem 0}
.prose li::marker{color:var(--amber)}
.prose strong{color:var(--fg)}
.button{align-self:flex-start;font:.8rem var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--blue);border:1px solid var(--blue);padding:.65rem 1rem;text-decoration:none;transition:background-color .2s,color .2s,box-shadow .2s}
.button:hover,.button:focus-visible{background:var(--blue);color:var(--bg);box-shadow:0 0 18px color-mix(in srgb,var(--blue) 55%,transparent)}
@keyframes marquee{to{transform:translateX(-50%)}}
@keyframes pulse{50%{opacity:.35}}
@keyframes blink{50%{opacity:0}}
@keyframes nudge{50%{transform:translateY(-2px)}}
@keyframes cascade{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){*,::before,::after{animation:none!important;transition:none!important}
.log li{opacity:1}.ticker{overflow-x:auto}.brief:hover,.brief:focus-within{transform:none}}
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


def key_point(body):
    """First bullet of the report (its Key Data section), as inline HTML."""
    return next((inline(line.strip()[2:]) for line in body.splitlines() if line.strip()[:2] in ("- ", "* ")), "")


def parse_date(date):
    try:
        d = datetime.fromisoformat(date)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def stamp(date):
    d = parse_date(date)
    label = f"{d.astimezone(timezone.utc):%Y-%m-%d %H:%M}Z" if d else date[:10]
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
            print(f"no quote for {label}: {e}", file=sys.stderr)  # the ticker just leaves that asset out
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
        "days": [f"{d:%m-%d}" for d in labels],
        "series": [{"name": n, "values": [counts[(n, d)] for d in labels]} for n in names],
    }


def ticker(quotes, synced):
    if not quotes:
        return ""
    items = "".join(
        f'<li><span class="sym">{label}</span><span class="px">{px}</span>'
        f'<span class="{"up" if chg >= 0 else "down"}"><i aria-hidden="true">{"▲" if chg >= 0 else "▼"}</i> {chg:+.2f}%</span></li>'
        for label, px, chg in quotes
    )
    track = f'<li class="asof">MARKETS @ {synced}</li>{items}'
    return (
        f'<div class="ticker" role="region" aria-label="Market snapshot at {synced}">'
        f'<div class="ticker-rail"><ul>{track}</ul><ul aria-hidden="true">{track}</ul></div></div>'
    )


def masthead(root, quotes, synced, built):
    return f"""<header class="masthead">
<div class="wrap bar">
<a class="brand" href="{root}index.html"><b>&#9698;</b> {SITE_TITLE}<span class="cursor" aria-hidden="true">_</span></a>
<p class="status"><span><span class="dot" aria-hidden="true"></span>Feed: <b>Online</b></span><span>Sources: {len(FEEDS)}</span>
<span>Last sync: <time datetime="{built.isoformat()}">{synced}</time></span><span>UTC <time id="clock">{built:%H:%M:%S}</time></span></p>
</div>
{ticker(quotes, synced)}
</header>"""


def page(title, content, root, header):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{html.escape(title)}</title>
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


def brief(s, now, heading="h3", extra=""):
    new = '<span class="flag">&#9679; New</span>' if s["dt"] and now - s["dt"] < timedelta(hours=NEW_HOURS) else ""
    return (
        f'<article class="panel brief{extra}">'
        f'<p class="brief-head"><span class="badge">{s["topic"]}</span><span class="src">{html.escape(s["source"])}</span>{new}</p>'
        f'<{heading}><a href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></{heading}>'
        f'<p class="summary">{html.escape(s["summary"])}</p>'
        f'<p class="meta">{stamp(s["date"])} · {s["minutes"]} min read · Brief #{s["slug"][-6:].upper()}</p></article>'
    )


def chart_panel(series):
    colors = ["--blue", "--amber", "--red", "--green"]
    legend = "".join(f'<li style="--c:var({c})">{html.escape(s["name"])}</li>' for s, c in zip(series["series"], colors))
    totals = ", ".join(f'{s["name"]} {sum(s["values"])}' for s in series["series"]) or "no stories"
    return (
        f'<section class="panel" aria-labelledby="chart-title">'
        f'<h2 class="panel-title" id="chart-title"><span>Macro coverage // stories per topic</span><b>{CHART_DAYS}D</b></h2>'
        f'<div class="chart-wrap"><canvas id="coverage-chart" role="img" aria-label="Stories per day over the last {CHART_DAYS} days: {totals}"></canvas>'
        f'<div class="chart-tip" id="chart-tip" hidden></div></div><ul class="legend">{legend}</ul>'
        f'<script type="application/json" id="coverage-data">{json.dumps(series).replace("</", "<\\/")}</script></section>'
    )


def sidebar(stories):
    log = "".join(
        f'<li style="--i:{i}">{stamp(s["date"])} <span class="lvl">[{s["topic"].upper()}]</span> '
        f'<a href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></li>'
        for i, s in enumerate(stories[:12])
    )
    points = "".join(f"<li>{s['point']}</li>" for s in stories[:6] if s["point"])
    return (
        f'<aside class="sidebar">'
        f'<section class="panel" aria-labelledby="log-title"><h2 class="panel-title" id="log-title"><span>System log // terminal feed</span><b>LIVE</b></h2>'
        f'<ol class="log">{log}<li class="prompt" style="--i:{min(len(stories), 12)}">&gt; awaiting next sync<span class="cursor">_</span></li></ol></section>'
        f'<section class="panel" aria-labelledby="points-title"><h2 class="panel-title" id="points-title"><span>Key data</span><b>{len(stories[:6])}</b></h2>'
        f'<ul class="points">{points}</ul></section></aside>'
    )


def article_page(s):
    url = s["url"]
    button = (
        f'<a class="button" href="{html.escape(url)}" target="_blank" rel="noopener">Read primary source &#8599;</a>'
        if url.startswith(("https://", "http://")) else ""
    )
    return (
        f'<main class="story"><article>\n<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Home</a>'
        f'<span aria-hidden="true">/</span><span aria-current="page">{s["topic"]}</span></nav>\n'
        f'<header><p class="brief-head"><span class="badge">{s["topic"]}</span><span class="src">{html.escape(s["source"])}</span></p>\n'
        f'<h1>{html.escape(s["title"])}</h1>\n'
        f'<p class="meta">{stamp(s["date"])} · {s["minutes"]} min read · Brief #{s["slug"][-6:].upper()}</p>\n{button}\n</header>\n'
        f'<div class="prose">\n{s["body"]}\n</div>\n</article></main>'
    )


def main():
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)  # generated output; a clean rebuild drops pages of deleted articles
    (PUBLIC / "articles").mkdir(parents=True)
    (PUBLIC / "style.css").write_text(CSS, encoding="utf-8")
    shutil.copyfile(APP_JS, PUBLIC / "app.js")

    built = datetime.now(timezone.utc)
    synced = f"{built:%Y-%m-%d %H:%M} UTC"
    quotes = market_quotes()
    stories = []
    for path in ARTICLES.glob("*.md"):
        meta, body = parse_article(path.read_text(encoding="utf-8"))
        title, summary, url = meta.get("title", path.stem), meta.get("summary", ""), meta.get("source_url", "")
        stories.append({
            "slug": path.stem, "title": title, "summary": summary, "date": meta.get("date", ""), "dt": parse_date(meta.get("date", "")),
            "url": url, "source": source_name(url), "topic": topic_of(title, summary), "minutes": read_minutes(body),
            "body": markdown(body), "point": key_point(body),
        })
    stories.sort(key=lambda s: s["date"], reverse=True)

    for s in stories:
        header = masthead("../", quotes, synced, built)
        (PUBLIC / "articles" / f"{s['slug']}.html").write_text(page(s["title"], article_page(s), "../", header), encoding="utf-8")

    if stories:
        # the newest story leads; the home page shows 10, older articles keep their pages and stay in the log
        lead, rest = stories[0], stories[1:10]
        primary = (
            f'<div class="primary">{chart_panel(coverage_series(stories, built.date()))}\n'
            f'<section aria-label="Lead story">{brief(lead, built, "h2", " lead")}</section>\n'
            f'<section aria-labelledby="briefs-title"><h2 class="sr-only" id="briefs-title">Latest briefs</h2>'
            f'<div class="briefs">' + "".join(brief(s, built) for s in rest) + "</div></section></div>"
        )
        content = f'<main class="wrap hud"><h1 class="sr-only">{SITE_TITLE}</h1>\n{primary}\n{sidebar(stories)}\n</main>'
    else:
        content = '<main class="wrap hud"><p>No stories yet.</p></main>'
    (PUBLIC / "index.html").write_text(page(SITE_TITLE, content, "", masthead("", quotes, synced, built)), encoding="utf-8")
    print(f"built {len(stories)} articles into {PUBLIC.relative_to(ROOT)}/ ({len(quotes)} market quotes)")


if __name__ == "__main__":
    main()
