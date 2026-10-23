"""Build public/ (index, article pages, style.css, app.js, search.json, feed.xml) from content/articles/*.md."""
import email.utils
import hashlib
import html
import json
import math
import random
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
APP_JS = Path(__file__).with_name("app.js")
SITE_TITLE = "World Economy Watch"
SITE_URL = "https://ismaelhugoo05.github.io/economic-news/"  # absolute links in feed.xml
DESK = "Global Desk"
FRONT_PAGE = 10  # lead + 9 cards shown before any filter is applied
FILTER_POOL = 60  # most recent stories rendered on the front page so topic filters have something to show
FEED_ITEMS = 30

SOURCES = {
    "cnbc.com": "CNBC", "marketwatch.com": "MarketWatch", "federalreserve.gov": "Federal Reserve",
    "finance.yahoo.com": "Yahoo Finance", "worldbank.org": "World Bank",
}

# (label, Yahoo symbol, price format); quotes and 1-month history are a build-time snapshot, not a live feed
MARKETS = [
    ("S&P 500", "^GSPC", "{:,.2f}"),
    ("US 10Y", "^TNX", "{:.3f}%"),
    ("Crude Oil", "CL=F", "${:,.2f}"),
    ("Gold", "GC=F", "${:,.2f}"),
    ("EUR/USD", "EURUSD=X", "{:.4f}"),
]

# shortcut: first keyword hit (title before summary) picks the tag; upgrade to a classifier if tags look wrong
TOPICS = [
    (name, re.compile(rf"\b({words})\b", re.I))
    for name, words in [
        ("Inflation", r"inflation|inflationary|cpi|ppi|consumer prices"),
        ("Central Banks", r"fed|federal reserve|ecb|central banks?|rate (hike|cut)s?|interest rates?|rates"),
        ("Energy", r"oil|crude|energy|opec|gasoline|natural gas"),
        ("Trade", r"tariffs?|trade|exports?|imports?"),
        ("Fiscal", r"deficit|budget|debt|treasury|imf"),
        ("Labor", r"jobs|payrolls|unemployment|wages|labor"),
        ("Growth", r"gdp|growth|recession|economy|housing"),
        ("Markets", r"yields?|bonds?|stocks?|shares|dollar|currenc(y|ies)|markets?"),
    ]
]
TAGS = {  # topic -> (hashtag, css class)
    "Inflation": ("#INFLATION", "rose"), "Central Banks": ("#POLICY", "indigo"), "Energy": ("#ENERGY", "amber"),
    "Trade": ("#TRADE", "sky"), "Fiscal": ("#FISCAL", "violet"), "Labor": ("#LABOR", "teal"),
    "Growth": ("#GROWTH", "emerald"), "Markets": ("#MARKETS", "blue"), "Economy": ("#ECONOMY", "slate"),
}
# header filters: (id, label, topics it covers); topics outside every filter show under "All" only
FILTERS = [
    ("markets", "Markets", {"Markets"}),
    ("policy", "Policy", {"Central Banks", "Fiscal"}),
    ("commodities", "Commodities", {"Energy"}),
    ("trade", "Global Trade", {"Trade"}),
]

FONTS = (
    "https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600;6..72,700;6..72,800"
    "&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap"
)

CSS = """\
:root{color-scheme:light;--canvas:#f8fafc;--card:#fff;--ink:#0f172a;--text:#334155;--muted:#64748b;--border:#e2e8f0;
--navy:#0b132b;--navy-2:#111c3d;--on-navy:#fff;--on-navy-muted:#a5b4cc;--amber:#f59e0b;--amber-ink:#451a03;
--up:#059669;--down:#e11d48;--up-on-navy:#34d399;--down-on-navy:#fb7185;--live:#34d399;
--rose:#be123c;--indigo:#4338ca;--amber-tag:#92400e;--sky:#0369a1;--violet:#6d28d9;--teal:#0f766e;--emerald:#047857;--blue:#1d4ed8;--slate:#475569;
--wave-0:#1e2a5a;--wave-1:#3730a3;--wave-2:#4f46e5;--wave-3:#7c3aed;--wave-4:#f59e0b;--mesh:#a5b4fc;
--shadow:0 8px 24px rgba(15,23,42,.06);--shadow-hover:0 16px 36px rgba(15,23,42,.12);--shadow-pop:0 24px 64px rgba(15,23,42,.28);
--display:Newsreader,Georgia,serif;--sans:"Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--canvas);color:var(--text);font:1rem/1.6 var(--sans);-webkit-font-smoothing:antialiased}
a{color:inherit}
button{font:inherit;color:inherit}
h1,h2,h3{font-family:var(--display);color:var(--ink);margin:0;line-height:1.12;letter-spacing:-.01em;text-wrap:balance}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.wrap{max-width:78rem;margin:0 auto;padding:0 1.25rem}
:focus-visible{outline:2px solid var(--amber);outline-offset:2px}
.site-header{position:sticky;top:0;z-index:50;color:var(--on-navy);background:color-mix(in srgb,var(--navy) 84%,transparent);
-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-bottom:1px solid color-mix(in srgb,var(--on-navy) 10%,transparent)}
.bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.6rem 1.5rem;padding-block:.85rem}
.brand{display:flex;align-items:center;gap:.75rem;text-decoration:none}
.brand-name{font:800 clamp(1.35rem,3vw,1.85rem)/1 var(--display);letter-spacing:-.015em;color:var(--on-navy)}
.edition{white-space:nowrap;font:700 .66rem/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--amber-ink);background:var(--amber);border-radius:999px;padding:.38rem .6rem}
.bar-end{display:flex;flex-wrap:wrap;align-items:center;gap:.6rem 1rem}
.status{display:inline-flex;align-items:center;gap:.45rem;font-size:.75rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--on-navy-muted)}
.dot{width:.5rem;height:.5rem;border-radius:50%;background:var(--live);animation:pulse 2s ease-out infinite}
.icon-btn{display:inline-flex;align-items:center;gap:.45rem;cursor:pointer;font-size:.8125rem;font-weight:600;color:var(--on-navy);
background:color-mix(in srgb,var(--on-navy) 8%,transparent);border:1px solid color-mix(in srgb,var(--on-navy) 16%,transparent);border-radius:999px;padding:.4rem .8rem;transition:background-color .2s}
.icon-btn:hover{background:color-mix(in srgb,var(--on-navy) 16%,transparent)}
.icon-btn svg{width:15px;height:15px}
kbd{font:600 .7rem var(--sans);border:1px solid color-mix(in srgb,currentColor 35%,transparent);border-radius:4px;padding:0 .3rem}
.filters{display:flex;gap:.4rem;margin:0;padding:0 0 .75rem;list-style:none;overflow-x:auto;scrollbar-width:none}
.filters::-webkit-scrollbar{display:none}
.filters a{display:block;white-space:nowrap;text-decoration:none;font-size:.8125rem;font-weight:600;color:var(--on-navy-muted);border-radius:999px;padding:.35rem .85rem;transition:color .2s,background-color .2s}
.filters a:hover{color:var(--on-navy)}
.filters a[aria-current="true"]{color:var(--navy);background:var(--on-navy)}
.ribbon{background:var(--navy-2);color:var(--on-navy);overflow-x:auto;scrollbar-width:none}
.ribbon::-webkit-scrollbar{display:none}
.ribbon ul{display:flex;gap:2rem;margin:0;padding:.7rem 0;list-style:none;white-space:nowrap}
.ribbon li{display:flex;align-items:center;gap:.75rem}
.quote{display:grid;line-height:1.3;font-variant-numeric:tabular-nums}
.quote .sym{font-size:.72rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--on-navy-muted)}
.quote .px{font-weight:700;color:var(--on-navy)}
.quote .chg{font-size:.75rem;font-weight:600}
.ribbon .up{color:var(--up-on-navy)}
.ribbon .down{color:var(--down-on-navy)}
.ribbon .asof{font-size:.75rem;color:var(--on-navy-muted)}
.spark{display:block;overflow:visible}
.spark .line{fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.spark.up .line{stroke:var(--up-on-navy)}
.spark.down .line{stroke:var(--down-on-navy)}
.spark .area{stroke:none;opacity:.18}
.spark.up .area{fill:var(--up-on-navy)}
.spark.down .area{fill:var(--down-on-navy)}
.progress{position:fixed;top:0;left:0;right:0;z-index:60;height:2px;background:var(--amber);transform:scaleX(0);transform-origin:0 50%}
.layout{display:grid;gap:2rem;padding-block:2.25rem 4rem}
@media (min-width:64rem){.layout{grid-template-columns:minmax(0,1fr) 20rem;align-items:start}}
.card{position:relative;background:var(--card);border:1px solid var(--border);border-radius:10px;box-shadow:var(--shadow);
transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease}
a.card-link{text-decoration:none}
a.card-link::after{content:"";position:absolute;inset:0;border-radius:10px}
a.card-link:focus-visible{outline:none}
.card:has(a.card-link:focus-visible){outline:2px solid var(--indigo);outline-offset:3px}
.card:hover{transform:translateY(-4px);box-shadow:var(--shadow-hover);border-color:color-mix(in srgb,var(--indigo) 25%,var(--border))}
.card:hover h2,.card:hover h3{color:var(--indigo)}
.tag{display:inline-block;justify-self:start;align-self:flex-start;font:700 .7rem/1 var(--sans);letter-spacing:.08em;color:var(--t);background:color-mix(in srgb,var(--t) 12%,transparent);
border:1px solid color-mix(in srgb,var(--t) 22%,transparent);border-radius:999px;padding:.4rem .7rem}
.tag.rose{--t:var(--rose)}.tag.indigo{--t:var(--indigo)}.tag.amber{--t:var(--amber-tag)}.tag.sky{--t:var(--sky)}.tag.violet{--t:var(--violet)}
.tag.teal{--t:var(--teal)}.tag.emerald{--t:var(--emerald)}.tag.blue{--t:var(--blue)}.tag.slate{--t:var(--slate)}
.meta{margin:0;font-size:.8125rem;color:var(--muted)}
.meta b{color:var(--ink);font-weight:600}
.lead{overflow:hidden}
.lead-art{display:block;width:100%;height:clamp(150px,22vw,240px);background:var(--navy)}
.lead-art .w{transform-box:fill-box;animation:drift 16s ease-in-out infinite alternate}
.lead-art .w1{animation-duration:19s}.lead-art .w2{animation-duration:23s}.lead-art .w3{animation-duration:17s}.lead-art .w4{animation-duration:21s}
.lead-art .w0{fill:var(--wave-0)}.lead-art .w1{fill:var(--wave-1);opacity:.85}.lead-art .w2{fill:var(--wave-2);opacity:.7}
.lead-art .w3{fill:var(--wave-3);opacity:.55}.lead-art .w4{fill:none;stroke:var(--wave-4);stroke-width:2.5;opacity:.9}
.lead-art .mesh{stroke:var(--mesh);stroke-width:1;opacity:.14}
.lead-art .node{fill:var(--mesh);opacity:.6}
.lead-body{display:grid;gap:1rem;padding:clamp(1.5rem,3.5vw,2.5rem)}
.lead h2{font-size:clamp(2rem,4.2vw,3.25rem);font-weight:800}
.standfirst{margin:0;font-size:1.125rem;line-height:1.65;max-width:62ch}
.section-title{display:flex;align-items:center;gap:.75rem;margin:2.5rem 0 1.25rem;font:800 .8125rem/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--ink)}
.section-title::before{content:"";width:1.5rem;height:3px;border-radius:2px;background:var(--amber)}
.filtering .lead-section{display:none}
.filtering .section-title{margin-top:0}
.cards{display:grid;gap:1.25rem;margin:0;padding:0;list-style:none}
@media (min-width:44rem){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
.cards:not(.filtered) > li:first-child,.cards:not(.filtered) > li:nth-child(n+11),.cards.filtered > li:not(.match){display:none}
.empty{margin:0;padding:2rem;text-align:center;color:var(--muted)}
.story{display:flex;flex-direction:column;gap:.75rem;padding:1.4rem 1.5rem}
.story h3{font-size:1.35rem;font-weight:700;transition:color .2s}
.story p.summary{margin:0;font-size:.9375rem}
.story .meta{margin-top:auto}
.side{display:grid;gap:1.25rem}
@media (min-width:64rem){.side{position:sticky;top:7.5rem}}
.widget{padding:1.4rem 1.5rem}
.widget h2{font:800 .8125rem/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;margin-bottom:.35rem}
.dial{display:block;width:100%;max-width:260px;margin:.75rem auto .25rem}
.dial .track{fill:none;stroke:url(#dial-grad);stroke-width:14;stroke-linecap:round}
.dial .needle{stroke:var(--ink);stroke-width:4;stroke-linecap:round;transform-box:view-box;transform-origin:100px 100px;
transform:rotate(var(--a));animation:sweep 1.6s cubic-bezier(.2,.8,.2,1) both}
.dial .hub{fill:var(--ink)}
.dial .scale{font:600 9px var(--sans);fill:var(--muted)}
.dial-grad-down{stop-color:var(--down)}.dial-grad-mid{stop-color:var(--amber)}.dial-grad-up{stop-color:var(--up)}
.stance{margin:0;text-align:center;font:800 1.35rem/1.2 var(--display);color:var(--ink)}
.stance-note{margin:.35rem 0 1rem;text-align:center;font-size:.8125rem;color:var(--muted)}
.movers{display:grid;gap:.45rem;margin:0;padding:1rem 0 0;list-style:none;border-top:1px solid var(--border);font-size:.8125rem;font-variant-numeric:tabular-nums}
.movers li{display:flex;justify-content:space-between}
.movers .up{color:var(--up);font-weight:600}
.movers .down{color:var(--down);font-weight:600}
.article-wrap{max-width:48rem;margin:0 auto;padding:2.25rem 1.25rem 4rem}
.crumbs{margin:0 0 1rem;font-size:.8125rem;color:var(--muted)}
.crumbs a{text-decoration:none;font-weight:600;color:var(--indigo)}
.crumbs a:hover{text-decoration:underline}
.article{padding:clamp(1.5rem,4vw,3rem)}
.article:hover{transform:none;box-shadow:var(--shadow);border-color:var(--border)}
.article header{display:grid;gap:1rem;justify-items:start;padding-bottom:1.75rem;margin-bottom:1.75rem;border-bottom:1px solid var(--border)}
.article h1{font-size:clamp(2rem,4.5vw,3rem);font-weight:800}
.actions{display:flex;flex-wrap:wrap;gap:.6rem}
.button{display:inline-flex;align-items:center;gap:.4rem;cursor:pointer;font:700 .875rem var(--sans);color:var(--on-navy);background:var(--navy);border:0;border-radius:999px;
padding:.7rem 1.2rem;text-decoration:none;transition:background-color .2s,transform .2s}
.button:hover{background:var(--indigo);transform:translateY(-1px)}
.button.ghost{color:var(--ink);background:transparent;border:1px solid var(--border)}
.button.ghost:hover{background:var(--canvas)}
.button.done{color:var(--emerald);border-color:color-mix(in srgb,var(--emerald) 40%,var(--border))}
.exec{margin:0 0 2rem;padding:1.25rem 1.5rem;border-radius:10px;background:color-mix(in srgb,var(--amber) 9%,var(--card));border:1px solid color-mix(in srgb,var(--amber) 35%,var(--border));border-left-width:4px}
.exec h2{font:800 .75rem/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--amber-tag);margin-bottom:.85rem}
.exec ol{margin:0;padding-left:1.25rem;display:grid;gap:.6rem;font-size:.9875rem;color:var(--ink)}
.exec li::marker{font-weight:800;color:var(--amber-tag)}
.prose{font:1.1875rem/1.8 var(--display);color:var(--text)}
.prose h2,.prose h3{margin:2.25rem 0 .75rem;font:800 .9rem/1.3 var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--ink)}
.prose p,.prose ul{margin:0 0 1.25rem}
.prose ul{padding-left:1.25rem}
.prose li{margin:.5rem 0}
.prose li::marker{color:var(--amber)}
.prose strong{color:var(--ink)}
.prose a{color:var(--indigo)}
dialog{border:0;padding:0;color:var(--text);background:var(--card);box-shadow:var(--shadow-pop)}
dialog::backdrop{background:rgb(11 19 43/.45);-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
.search-dialog{width:min(40rem,calc(100% - 2rem));margin-top:12vh;border-radius:14px}
.search-head{display:flex;align-items:center;gap:.75rem;padding:1rem 1.25rem;border-bottom:1px solid var(--border)}
.search-head svg{width:18px;height:18px;color:var(--muted);flex:none}
.search-head input{flex:1;min-width:0;border:0;outline:0;font:500 1.0625rem var(--sans);color:var(--ink);background:transparent}
.close{cursor:pointer;border:1px solid var(--border);background:var(--card);border-radius:8px;padding:.25rem .55rem;font-size:.75rem;font-weight:600;color:var(--muted)}
.results{max-height:min(60vh,32rem);overflow:auto;margin:0;padding:.5rem;list-style:none}
.results a{display:grid;gap:.2rem;padding:.75rem .85rem;border-radius:8px;text-decoration:none}
.results a:hover,.results a:focus-visible{background:var(--canvas);outline:none}
.results strong{font:700 1.05rem/1.3 var(--display);color:var(--ink)}
.results span{font-size:.8125rem;color:var(--muted)}
.results .hint{padding:1rem .85rem;font-size:.875rem;color:var(--muted)}
mark{background:color-mix(in srgb,var(--amber) 35%,transparent);color:inherit;border-radius:2px}
.drawer{margin:0 0 0 auto;width:min(30rem,100%);height:100dvh;max-height:none;border-radius:0;overflow:auto}
.drawer[open]{animation:slide-in .3s ease-out}
.drawer-body{padding:1.75rem 1.75rem 3rem}
.drawer-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem}
.drawer h2{font-size:1.75rem;font-weight:800}
.drawer h3{font:800 .8125rem/1.2 var(--sans);letter-spacing:.1em;text-transform:uppercase;margin:1.75rem 0 .5rem}
.drawer p,.drawer li{font-size:.9375rem}
.drawer ol{padding-left:1.25rem;display:grid;gap:.75rem}
.drawer .disclaimer{margin-top:1.75rem;padding:1rem 1.15rem;border-radius:10px;background:var(--canvas);border:1px solid var(--border);font-size:.875rem}
.site-footer{margin-top:2rem;background:var(--navy);color:var(--on-navy-muted);font-size:.875rem}
.footer-grid{display:grid;gap:2rem;padding-block:3rem 2rem}
@media (min-width:48rem){.footer-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:68rem){.footer-grid{grid-template-columns:1.4fr 1fr 1fr 1.4fr}}
.site-footer h2{font:800 .75rem/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--on-navy);margin-bottom:1rem}
.site-footer .brand-name{display:block;margin-bottom:.75rem}
.site-footer p{margin:0 0 .75rem}
.site-footer ul{margin:0;padding:0;list-style:none;display:grid;gap:.5rem}
.site-footer a,.link-btn{color:var(--on-navy);text-decoration:none}
.site-footer a:hover,.link-btn:hover{text-decoration:underline}
.link-btn{cursor:pointer;background:none;border:0;padding:0;font-size:.875rem}
.footer-base{border-top:1px solid color-mix(in srgb,var(--on-navy) 12%,transparent);padding-block:1.25rem 2rem;font-size:.8125rem}
@keyframes drift{from{transform:translateX(-24px)}to{transform:translateX(24px)}}
@keyframes sweep{from{transform:rotate(-90deg)}}
@keyframes pulse{0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--live) 70%,transparent)}100%{box-shadow:0 0 0 .5rem transparent}}
@keyframes slide-in{from{transform:translateX(100%)}}
@media (prefers-reduced-motion:reduce){*,::backdrop{animation:none!important;transition:none!important}.card:hover{transform:none}}
"""

SEARCH_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>'


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


def key_points(body, n=3):
    """The report's first n bullet points (its Key Data section), as inline HTML."""
    return [inline(line.strip()[2:]) for line in body.splitlines() if line.strip()[:2] in ("- ", "* ")][:n]


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


def filters_for(topic):
    return [fid for fid, _, topics in FILTERS if topic in topics]


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


def short_date(s):
    d = parse_date(s["date"])
    return f"{d:%b} {d.day}, {d.year}" if d else s["date"][:10]


def meta_line(s):
    return (f'<p class="meta"><b>{DESK}</b> · <time datetime="{html.escape(s["date"])}">{html.escape(short_date(s))}</time>'
            f' · {s["minutes"]} min read</p>')


def tag(topic):
    label, color = TAGS.get(topic, TAGS["Economy"])
    return f'<span class="tag {color}">{label}</span>'


def closes(chart):
    """Daily closes from a Yahoo chart response, oldest first, gaps dropped."""
    series = [c for c in chart["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c is not None]
    if len(series) < 2:
        raise ValueError("fewer than two closes")
    return series


def market_quotes():
    quotes = []
    for label, symbol, fmt in MARKETS:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=1mo&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (econ-news-pipeline)"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                series = closes(json.load(r))
        except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
            print(f"no quote for {label}: {e}", file=sys.stderr)  # the ribbon and dial just leave that asset out
            continue
        day = (series[-1] - series[-2]) / series[-2] * 100
        month = (series[-1] - series[0]) / series[0] * 100
        quotes.append({"label": label, "price": fmt.format(series[-1]), "day": day, "month": month, "series": series})
    return quotes


def sparkline(values, width=84, height=28):
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1)
    points = [(i * step, height - 2 - (v - lo) / span * (height - 4)) for i, v in enumerate(values)]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    trend = "up" if values[-1] >= values[0] else "down"
    return (
        f'<svg class="spark {trend}" viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true">'
        f'<path class="area" d="{line} L{width},{height} L0,{height} Z"/><path class="line" d="{line}"/></svg>'
    )


def ribbon(quotes, synced):
    if not quotes:
        return ""
    items = "".join(
        f'<li><span class="quote"><span class="sym">{q["label"]}</span><span class="px">{q["price"]}</span>'
        f'<span class="chg {"up" if q["day"] >= 0 else "down"}">{"▲" if q["day"] >= 0 else "▼"} {abs(q["day"]):.2f}%</span></span>'
        f'{sparkline(q["series"])}</li>'
        for q in quotes
    )
    return (
        f'<div class="ribbon" role="region" aria-label="Markets"><div class="wrap"><ul>{items}'
        f'<li class="asof">1-month trend · as of {synced}</li></ul></div></div>'
    )


def stance(quotes):
    """(benchmarks higher over the month, total, label) — a plain breadth count, not a forecast."""
    rising = sum(q["month"] >= 0 for q in quotes)
    share = rising / len(quotes)
    label = "Broadly higher" if share >= 0.7 else "Broadly lower" if share <= 0.3 else "Mixed"
    return rising, len(quotes), label


def stance_dial(quotes):
    if not quotes:
        return ""
    rising, total, label = stance(quotes)
    angle = -90 + 180 * rising / total
    movers = "".join(
        f'<li><span>{q["label"]}</span><span class="{"up" if q["month"] >= 0 else "down"}">'
        f'{"▲" if q["month"] >= 0 else "▼"} {abs(q["month"]):.1f}%</span></li>'
        for q in quotes
    )
    return f"""<section class="card widget" aria-labelledby="stance-title">
<h2 id="stance-title">Market stance</h2>
<p class="meta">How many tracked benchmarks rose over the past month</p>
<svg class="dial" viewBox="0 0 200 118" role="img" aria-label="{rising} of {total} benchmarks higher over the past month: {label}">
<defs><linearGradient id="dial-grad" x1="0" x2="1"><stop offset="0" class="dial-grad-down"/><stop offset=".5" class="dial-grad-mid"/><stop offset="1" class="dial-grad-up"/></linearGradient></defs>
<path class="track" d="M20 100 A80 80 0 0 1 180 100"/>
<line class="needle" x1="100" y1="100" x2="100" y2="34" style="--a:{angle:.0f}deg"/>
<circle class="hub" cx="100" cy="100" r="7"/>
<text class="scale" x="14" y="117">Lower</text><text class="scale" x="186" y="117" text-anchor="end">Higher</text>
</svg>
<p class="stance">{label}</p>
<p class="stance-note">{rising} of {total} benchmarks higher over 1 month</p>
<ul class="movers">{movers}</ul>
</section>"""


def wave_art(seed_text):
    """Decorative wave mesh, unique per story but stable across builds."""
    rnd = random.Random(int(hashlib.sha1(seed_text.encode()).hexdigest(), 16))
    waves = []
    for k in range(5):
        amp, freq, phase, base = rnd.uniform(14, 36), rnd.uniform(1.1, 2.4), rnd.uniform(0, 2 * math.pi), 95 + k * 42
        points = " L".join(f"{x},{base + amp * math.sin(freq * x / 1200 * 2 * math.pi + phase):.1f}" for x in range(-60, 1261, 30))
        closing = "" if k == 4 else " L1260,330 L-60,330 Z"  # the top layer is an open line, not a filled band
        waves.append(f'<path class="w w{k}" d="M{points}{closing}"/>')
    mesh = "".join(f'<path class="mesh" d="M{x},0 L{x - 160},320"/>' for x in range(80, 1400, 80))
    nodes = "".join(f'<circle class="node" cx="{rnd.uniform(40, 1160):.0f}" cy="{rnd.uniform(20, 140):.0f}" r="{rnd.uniform(1.5, 3.2):.1f}"/>' for _ in range(18))
    return (
        f'<svg class="lead-art" viewBox="0 0 1200 320" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
        f'{mesh}{"".join(waves)}{nodes}</svg>'
    )


def site_header(root, built):
    filters = "".join(
        f'<li><a href="{root}index.html?topic={fid}" data-filter="{fid}">{label}</a></li>' for fid, label, _ in FILTERS
    )
    return f"""<header class="site-header">
<div class="wrap bar">
<a class="brand" href="{root}index.html"><span class="brand-name">{SITE_TITLE}</span><span class="edition">Global Edition</span></a>
<div class="bar-end">
<span class="status"><span class="dot" aria-hidden="true"></span>Latest briefing · {built:%a}, {built:%b} {built.day}</span>
<button class="icon-btn" type="button" data-open="search" aria-label="Search reports">{SEARCH_ICON}<span>Search</span><kbd aria-hidden="true">/</kbd></button>
<button class="icon-btn" type="button" data-open="about">About &amp; Methodology</button>
</div>
</div>
<nav class="wrap" aria-label="Topics"><ul class="filters">
<li><a href="{root}index.html" data-filter="all">All</a></li>{filters}</ul></nav>
</header>"""


def dialogs(root):
    return f"""<dialog class="search-dialog" id="search" aria-labelledby="search-label">
<div class="search-head">{SEARCH_ICON}<label class="sr-only" id="search-label" for="search-input">Search reports</label>
<input id="search-input" type="search" placeholder="Search headlines, tags and summaries" autocomplete="off">
<button class="close" type="button" data-close>Esc</button></div>
<ul class="results" id="search-results" aria-live="polite"><li class="hint">Type to search every report.</li></ul>
</dialog>
<dialog class="drawer" id="about" aria-labelledby="about-title">
<div class="drawer-body">
<div class="drawer-top"><h2 id="about-title">About &amp; Methodology</h2><button class="close" type="button" data-close>Close</button></div>
<p>{SITE_TITLE} publishes short, data-first briefings on the global economy: inflation, central banks, trade, fiscal policy, energy and markets.
Each briefing is written by software from public primary-source reporting and linked back to that source.</p>
<h3 id="methodology">How a briefing is made</h3>
<ol>
<li><strong>Ingestion.</strong> Every day at 06:00 UTC an automated job reads public RSS feeds and news APIs from CNBC, MarketWatch,
the Federal Reserve, Yahoo Finance and the World Bank, and keeps stories about the macro economy.</li>
<li><strong>Machine synthesis.</strong> Google's Gemini model writes an original 400&ndash;500 word report for each story from the source
article's facts, under written editorial rules: use only figures that appear in the source, never invent numbers or quotes, and quote
only public officials on the record.</li>
<li><strong>Automated checks.</strong> A report is published only if it has the required structure (lead, Market Overview,
Macroeconomic Implications, Key Data &amp; Forecast) and length. Reports that fail are discarded, never replaced by the source teaser.</li>
<li><strong>Market data.</strong> Prices, sparklines and the market-stance dial are a snapshot from Yahoo Finance taken when the site
is built. They are not real-time.</li>
</ol>
<h3>What is not checked</h3>
<p>There is no human editor and no independent fact-check. A model can misread or misstate a figure. Every report links to its
primary source: check it before relying on any number.</p>
<p class="disclaimer"><strong>Disclaimer.</strong> Briefings are for analytical and educational purposes only. They are not investment,
financial, legal or tax advice, and they may contain errors or omissions. Do not make decisions based solely on this site.</p>
</div>
</dialog>"""


def site_footer(root, built):
    sectors = "".join(f"<li>{name}</li>" for name in ["Inflation", "Central banks &amp; policy", "Energy &amp; commodities",
                                                       "Global trade", "Fiscal policy", "Labor markets", "Growth", "Financial markets"])
    return f"""<footer class="site-footer">
<div class="wrap footer-grid">
<section><span class="brand-name">{SITE_TITLE}</span>
<p>Data-first briefings on the forces moving the global economy, each traced to its primary source.</p>
<p>Published daily at 06:00 UTC.</p>
<p><span class="status"><span class="dot" aria-hidden="true"></span>Last updated {built:%b} {built.day}, {built:%H:%M} UTC</span></p></section>
<section><h2>Coverage</h2><ul>{sectors}</ul></section>
<section><h2>Platform</h2><ul>
<li><button class="link-btn" type="button" data-open="about">About</button></li>
<li><button class="link-btn" type="button" data-open="about" data-target="methodology">Methodology</button></li>
<li><a href="{root}feed.xml">RSS feed</a></li></ul></section>
<section><h2>Legal</h2>
<p>For analytical and educational purposes only; not investment advice.</p>
<p><strong>AI disclosure:</strong> reports are written by Google's Gemini model from public sources, with automated structure checks
and no human fact-check.</p></section>
</div>
<div class="wrap footer-base">&copy; {built.year} {SITE_TITLE}. Source material belongs to the publishers credited in each report.</div>
</footer>"""


def page(title, content, root, built, quotes, article=False):
    synced = f"{built:%b} {built.day}, {built:%H:%M} UTC"
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
<link rel="alternate" type="application/rss+xml" title="{SITE_TITLE}" href="{root}feed.xml">
<script src="{root}app.js" defer></script>
</head>
<body data-root="{root}">
{'<div class="progress" aria-hidden="true"></div>' if article else ''}
{site_header(root, built)}
{ribbon(quotes, synced)}
{content}
{site_footer(root, built)}
{dialogs(root)}
</body>
</html>
"""


def lead_card(s):
    return (
        f'<article class="card lead">{wave_art(s["slug"])}<div class="lead-body">{tag(s["topic"])}'
        f'<h2><a class="card-link" href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></h2>'
        f'<p class="standfirst">{html.escape(sentences(s["summary"], 2))}</p>{meta_line(s)}</div></article>'
    )


def story_card(s):
    return (
        f'<li class="card story" data-filters="{" ".join(filters_for(s["topic"]))}">{tag(s["topic"])}'
        f'<h3><a class="card-link" href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></h3>'
        f'<p class="summary">{html.escape(sentences(s["summary"], 1))}</p>{meta_line(s)}</li>'
    )


def exec_summary(points):
    if not points:
        return ""
    return ('<aside class="exec" aria-labelledby="exec-title"><h2 id="exec-title">Executive summary</h2><ol>'
            + "".join(f"<li>{p}</li>" for p in points) + "</ol></aside>")


def article_page(s):
    url = s["url"]
    source = (
        f'<a class="button" href="{html.escape(url)}" target="_blank" rel="noopener">Primary source: {html.escape(s["source"])} &#8599;</a>'
        if url.startswith(("https://", "http://")) else ""
    )
    return (
        f'<main class="article-wrap"><p class="crumbs"><a href="../index.html">&larr; All briefings</a></p>\n'
        f'<article class="card article">\n<header>{tag(s["topic"])}\n<h1>{html.escape(s["title"])}</h1>\n{meta_line(s)}\n'
        f'<div class="actions">{source}<button class="button ghost" type="button" data-copy>Copy link</button></div>\n</header>\n'
        f'{exec_summary(s["points"])}\n<div class="prose">\n{s["body"]}\n</div>\n</article></main>'
    )


def search_index(stories):
    return [{"t": s["title"], "g": TAGS.get(s["topic"], TAGS["Economy"])[0], "s": sentences(s["summary"], 1),
             "d": short_date(s), "u": f'articles/{s["slug"]}.html'} for s in stories]


def rss_feed(stories, built):
    items = "".join(
        f"<item><title>{html.escape(s['title'])}</title><link>{SITE_URL}articles/{s['slug']}.html</link>"
        f"<guid>{SITE_URL}articles/{s['slug']}.html</guid>"
        + (f"<pubDate>{email.utils.format_datetime(d)}</pubDate>" if (d := parse_date(s["date"])) else "")
        + f"<category>{html.escape(s['topic'])}</category><description>{html.escape(sentences(s['summary'], 2))}</description></item>"
        for s in stories[:FEED_ITEMS]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        f"<title>{SITE_TITLE}</title><link>{SITE_URL}</link><description>Daily macroeconomic briefings</description>"
        f"<lastBuildDate>{email.utils.format_datetime(built)}</lastBuildDate>{items}</channel></rss>\n"
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
            "slug": path.stem, "title": title, "summary": summary, "date": meta.get("date", ""),
            "url": url, "source": source_name(url), "topic": topic_of(title, summary), "minutes": read_minutes(body),
            "body": markdown(body), "points": key_points(body),
        })
    stories.sort(key=lambda s: s["date"], reverse=True)

    for s in stories:
        (PUBLIC / "articles" / f"{s['slug']}.html").write_text(page(s["title"], article_page(s), "../", built, quotes, article=True), encoding="utf-8")

    if stories:
        # the grid holds the newest FILTER_POOL stories; CSS shows cards 2-10 until a topic filter is picked
        content = (
            f'<main class="wrap layout"><h1 class="sr-only">{SITE_TITLE}</h1>\n<div class="front">'
            f'<section class="lead-section" aria-label="Lead story">{lead_card(stories[0])}</section>\n'
            f'<section aria-labelledby="latest"><h2 class="section-title" id="latest">Latest reports</h2>'
            f'<ul class="cards" data-filterable>' + "".join(story_card(s) for s in stories[:FILTER_POOL]) + "</ul>"
            f'<p class="empty" hidden>No reports in this topic yet.</p></section></div>\n'
            f'<aside class="side">{stance_dial(quotes)}</aside>\n</main>'
        )
    else:
        content = '<main class="wrap layout"><p>No stories yet.</p></main>'
    (PUBLIC / "index.html").write_text(page(SITE_TITLE, content, "", built, quotes), encoding="utf-8")
    (PUBLIC / "search.json").write_text(json.dumps(search_index(stories), ensure_ascii=False), encoding="utf-8")
    (PUBLIC / "feed.xml").write_text(rss_feed(stories, built), encoding="utf-8")
    print(f"built {len(stories)} articles into {PUBLIC.relative_to(ROOT)}/ ({len(quotes)} market quotes)")


if __name__ == "__main__":
    main()
