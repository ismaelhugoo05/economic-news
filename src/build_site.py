"""Build public/ (index, article pages, style.css) from content/articles/*.md."""
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
PUBLIC = ROOT / "public"
SITE_TITLE = "Economic News"

CSS = """\
:root{color-scheme:light dark;--bg:#fff;--fg:#1a1a1a;--muted:#5f6368;--accent:#0b57d0;--line:#e3e3e3}
@media (prefers-color-scheme:dark){:root{--bg:#121212;--fg:#e8e8e8;--muted:#a0a0a0;--accent:#8ab4f8;--line:#2c2c2c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:1.0625rem/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:42rem;margin:0 auto;padding:2.5rem 1rem 4rem}
h1,h2,h3{line-height:1.25;text-wrap:balance}
h1{font-size:2rem;margin:0 0 .5rem}
a{color:var(--accent);text-underline-offset:.15em}
.meta{color:var(--muted);font-size:.875rem;margin:0}
.stories{list-style:none;padding:0;margin:2rem 0 0}
.stories li{padding:1.25rem 0;border-top:1px solid var(--line)}
.stories h2{font-size:1.25rem;margin:0 0 .25rem}
.stories h2 a{color:inherit;text-decoration:none}
.stories h2 a:hover{text-decoration:underline}
.stories p{margin:.5rem 0 0}
article header{margin-bottom:2rem}
nav{margin-bottom:2rem;font-size:.875rem}
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
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


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


def page(title, main, css):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{css}">
</head>
<body>
<main>
{main}
</main>
</body>
</html>
"""


def time_tag(date):
    return f'<time datetime="{html.escape(date)}">{html.escape(date[:10])}</time>'


def main():
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)  # generated output; a clean rebuild drops pages of deleted articles
    (PUBLIC / "articles").mkdir(parents=True)
    (PUBLIC / "style.css").write_text(CSS, encoding="utf-8")

    entries = []
    for path in ARTICLES.glob("*.md"):
        meta, body = parse_article(path.read_text(encoding="utf-8"))
        title, date = meta.get("title", path.stem), meta.get("date", "")
        article = (
            f'<nav><a href="../index.html">&larr; All stories</a></nav>\n<article>\n<header>\n'
            f"<h1>{html.escape(title)}</h1>\n<p class=\"meta\">{time_tag(date)}</p>\n</header>\n"
            f"{markdown(body)}\n</article>"
        )
        (PUBLIC / "articles" / f"{path.stem}.html").write_text(page(title, article, "../style.css"), encoding="utf-8")
        entries.append((date, path.stem, title, meta.get("summary", "")))

    items = "\n".join(
        f'<li><h2><a href="articles/{slug}.html">{html.escape(title)}</a></h2>'
        f'<p class="meta">{time_tag(date)}</p><p>{html.escape(summary)}</p></li>'
        for date, slug, title, summary in sorted(entries, reverse=True)
    )
    index = f'<h1>{SITE_TITLE}</h1>\n<p class="meta">{len(entries)} stories</p>\n<ul class="stories">\n{items}\n</ul>'
    (PUBLIC / "index.html").write_text(page(SITE_TITLE, index, "style.css"), encoding="utf-8")
    print(f"built {len(entries)} articles into {PUBLIC.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
