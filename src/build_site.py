"""Build public/ (index, article pages, style.css) from content/articles/*.md."""
import html
import json
import math
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
PUBLIC = ROOT / "public"
SITE_TITLE = "Economic News"

SOURCES = {"cnbc.com": "CNBC", "marketwatch.com": "MarketWatch"}

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

CSS = """\
:root{color-scheme:light;--bg:#fff1e5;--surface:#fff8f2;--ink:#141414;--body:#333;--muted:#66605b;--line:#ead8cb;
--accent:#990f3d;--accent-hover:#0f2537;--on-accent:#fff;--badge-bg:#f9e3e4;--badge-fg:#990f3d;--live:#16a34a;
--serif:Georgia,Merriweather,"Times New Roman",serif;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--body);font:1rem/1.6 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-underline-offset:.15em}
a:hover{color:var(--accent-hover)}
h1,h2,h3{font-family:var(--serif);font-weight:700;line-height:1.2;letter-spacing:-.01em;text-wrap:balance;color:var(--ink);margin:0}
.wrap{max-width:72rem;margin:0 auto;padding:0 1.25rem}
.masthead{border-bottom:1px solid var(--line)}
.masthead .wrap{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:.25rem 1.5rem;padding-block:1.25rem}
.brand,.brand:hover{font:700 1.85rem/1.1 var(--serif);letter-spacing:-.01em;color:var(--ink);text-decoration:none}
.dateline{margin:0;display:flex;flex-wrap:wrap;align-items:center;gap:.25rem 1rem;color:var(--muted);font-size:.8125rem}
.live{display:inline-flex;align-items:center;gap:.45rem;font-weight:600;color:var(--body)}
.live::before{content:"";width:.5rem;height:.5rem;border-radius:50%;background:var(--live);animation:pulse 2s ease-out infinite}
@keyframes pulse{from{box-shadow:0 0 0 0 color-mix(in srgb,var(--live) 55%,transparent)}to{box-shadow:0 0 0 .45rem transparent}}
main{padding-block:2rem 4rem}
.tags{margin:0;display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}
.badge{background:var(--badge-bg);color:var(--badge-fg);font-weight:600;font-size:.75rem;line-height:1;padding:.35rem .65rem;border-radius:999px}
.source{color:var(--muted);font-size:.7rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase}
.meta{margin:0;color:var(--muted);font-size:.8125rem}
.card{position:relative;display:flex;flex-direction:column;gap:.65rem;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:1.25rem;transition:transform .2s ease,border-color .2s ease,box-shadow .2s ease}
.card:hover{transform:translateY(-2px);border-color:var(--accent);box-shadow:0 8px 20px -12px color-mix(in srgb,var(--ink) 35%,transparent)}
.card h3{font-size:1.25rem}
.card :is(h1,h3) a{color:var(--ink);text-decoration:none;transition:color .2s ease}
.card:hover :is(h1,h3) a{color:var(--accent)}
.card a::after{content:"";position:absolute;inset:0}
.card:focus-within{outline:2px solid var(--accent);outline-offset:2px}
.card a:focus{outline:none}
.card .summary{margin:0}
.card .meta{margin-top:auto}
.lead{padding:clamp(1.5rem,4vw,3rem);border-top:3px solid var(--accent);margin-bottom:2.5rem;gap:1rem}
.lead h1{font-size:clamp(2rem,4.5vw,3.25rem);max-width:22ch}
.lead .summary{font-size:1.15rem;max-width:60ch}
.section-title{font:700 .75rem/1 var(--sans);text-transform:uppercase;letter-spacing:.12em;color:var(--ink);padding-bottom:.75rem;border-bottom:1px solid var(--line);margin-bottom:1.5rem}
.grid{display:grid;grid-template-columns:1fr;gap:1.25rem}
@media (min-width:40rem){.grid{grid-template-columns:repeat(2,1fr)}}
@media (min-width:64rem){.grid{grid-template-columns:repeat(3,1fr)}}
.story{max-width:720px;margin:0 auto;padding:0 1.25rem}
.crumbs{display:flex;gap:.5rem;font-size:.8125rem;color:var(--muted);margin-bottom:1.5rem}
.crumbs a{text-decoration:none}
.story header{display:flex;flex-direction:column;gap:1rem;padding-bottom:2rem;margin-bottom:2rem;border-bottom:1px solid var(--line)}
.story h1{font-size:clamp(2rem,5vw,2.75rem)}
.prose{font-size:1.125rem;line-height:1.75}
.prose h2,.prose h3{margin:2.25rem 0 .75rem;font-size:1.5rem}
.prose p,.prose ul{margin:0 0 1.25rem}
.prose ul{padding-left:1.25rem}
.prose li{margin:.5rem 0}
.button{align-self:flex-start;background:var(--accent);color:var(--on-accent);padding:.7rem 1.15rem;border-radius:6px;font-size:.875rem;font-weight:600;text-decoration:none;transition:background-color .2s ease}
.button:hover,.button:focus-visible{background:var(--accent-hover);color:var(--on-accent)}
@media (prefers-reduced-motion:reduce){*,::before{animation:none!important;transition:none!important}.card:hover{transform:none}}
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


def time_tag(date):
    try:
        d = datetime.fromisoformat(date)
        label = f"{d:%b} {d.day}, {d.year}"
    except ValueError:
        label = date[:10]
    return f'<time datetime="{html.escape(date)}">{html.escape(label)}</time>'


def tags(s):
    return f'<p class="tags"><span class="badge">{s["topic"]}</span><span class="source">{html.escape(s["source"])}</span></p>'


def card(s, heading="h3", extra=""):
    return (
        f'<article class="card{extra}">{tags(s)}'
        f'<{heading}><a href="articles/{s["slug"]}.html">{html.escape(s["title"])}</a></{heading}>'
        f'<p class="summary">{html.escape(s["summary"])}</p>'
        f'<p class="meta">{time_tag(s["date"])} · {s["minutes"]} min read</p></article>'
    )


def page(title, content, root):
    today = datetime.now()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header class="masthead"><div class="wrap">
<a class="brand" href="{root}index.html">{SITE_TITLE}</a>
<p class="dateline"><time datetime="{today:%Y-%m-%d}">{today:%A, %B} {today.day}, {today.year}</time><span class="live">Updated daily</span></p>
</div></header>
<main>
{content}
</main>
</body>
</html>
"""


def article_page(s):
    url = s["url"]
    button = (
        f'<a class="button" href="{html.escape(url)}" target="_blank" rel="noopener">Read Primary Source &#8599;</a>'
        if url.startswith(("https://", "http://")) else ""
    )
    return (
        f'<article class="story">\n<nav class="crumbs" aria-label="Breadcrumb"><a href="../index.html">Home</a>'
        f'<span aria-hidden="true">&rsaquo;</span><span aria-current="page">{s["topic"]}</span></nav>\n'
        f'<header>{tags(s)}\n<h1>{html.escape(s["title"])}</h1>\n'
        f'<p class="meta">{time_tag(s["date"])} · {s["minutes"]} min read</p>\n{button}\n</header>\n'
        f'<div class="prose">\n{s["body"]}\n</div>\n</article>'
    )


def main():
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)  # generated output; a clean rebuild drops pages of deleted articles
    (PUBLIC / "articles").mkdir(parents=True)
    (PUBLIC / "style.css").write_text(CSS, encoding="utf-8")

    stories = []
    for path in ARTICLES.glob("*.md"):
        meta, body = parse_article(path.read_text(encoding="utf-8"))
        title, summary = meta.get("title", path.stem), meta.get("summary", "")
        s = {
            "slug": path.stem, "title": title, "summary": summary, "date": meta.get("date", ""),
            "url": meta.get("source_url", ""), "source": source_name(meta.get("source_url", "")),
            "topic": topic_of(title, summary), "minutes": read_minutes(body), "body": markdown(body),
        }
        (PUBLIC / "articles" / f"{path.stem}.html").write_text(page(title, article_page(s), "../"), encoding="utf-8")
        stories.append(s)

    stories.sort(key=lambda s: s["date"], reverse=True)
    if stories:
        # the newest story leads; the home page shows 10, older articles keep their pages but drop off the index
        lead, rest = stories[0], stories[1:10]
        content = (
            f'<div class="wrap">\n<section aria-label="Lead story">{card(lead, "h1", " lead")}</section>\n'
            f'<section aria-labelledby="latest"><h2 id="latest" class="section-title">Latest</h2>\n'
            f'<div class="grid">\n' + "\n".join(card(s) for s in rest) + "\n</div></section>\n</div>"
        )
    else:
        content = '<div class="wrap"><p>No stories yet.</p></div>'
    (PUBLIC / "index.html").write_text(page(SITE_TITLE, content, ""), encoding="utf-8")
    print(f"built {len(stories)} articles into {PUBLIC.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
