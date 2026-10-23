import unittest

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from build_site import (
    CSP, CSS, article_page, closes, filters_for, key_points, lead_card, markdown, meta_line, page, parse_article, read_minutes,
    ribbon, rss_feed, search_index, sentences, source_name, sparkline, stance, stance_dial, story_card, tag, topic_of,
)

ARTICLE = """---
title: "Fed: \\"hold\\""
date: 2026-10-20T14:00:00+00:00
---

## Key Takeaway
- CPI **0.3%**, *core* 0.2%
- <script>x</script>

See [CNBC](https://cnbc.test/a?b=1&c=2) or [bad](javascript:alert(1)).
"""


class BuildSiteTest(unittest.TestCase):
    def test_parse_and_render(self):
        meta, body = parse_article(ARTICLE)
        self.assertEqual(meta, {"title": 'Fed: "hold"', "date": "2026-10-20T14:00:00+00:00"})
        out = markdown(body)
        self.assertIn("<h2>Key Takeaway</h2>", out)
        self.assertIn("<ul><li>CPI <strong>0.3%</strong>, <em>core</em> 0.2%</li><li>&lt;script&gt;x&lt;/script&gt;</li></ul>", out)
        self.assertIn('<a href="https://cnbc.test/a?b=1&amp;c=2" target="_blank" rel="noopener noreferrer">CNBC</a>', out)
        self.assertNotIn('href="javascript', out)

    def test_hostile_story_fields_are_escaped(self):
        s = {"slug": "2026-10-23-x-abc123", "title": '<img src=x onerror=alert(1)>', "summary": '"><script>alert(1)</script>',
             "date": "2026-10-23T22:00:00+00:00", "url": 'https://evil.test/"><script>x</script>', "source": "<b>src</b>",
             "topic": "Markets", "minutes": 1, "body": "", "points": []}
        out = page(s["title"], article_page(s) + story_card(s) + lead_card(s), "../", datetime(2026, 10, 24, tzinfo=timezone.utc), [])
        for raw in ("<img src=x", "<script>alert", "<script>x", "<b>src</b>"):
            self.assertNotIn(raw, out)
        self.assertIn('href="https://evil.test/&quot;&gt;&lt;script&gt;x&lt;/script&gt;" target="_blank" rel="noopener noreferrer"', out)
        self.assertNotIn("javascript:", article_page({**s, "url": "javascript:alert(1)"}))  # non-http(s) URLs get no button

    def test_security_headers_and_no_inline_styles_or_scripts(self):
        out = page("t", "<main></main>", "", datetime(2026, 10, 24, tzinfo=timezone.utc), [])
        self.assertIn(f'<meta http-equiv="Content-Security-Policy" content="{CSP}">', out)
        self.assertIn("script-src 'self';", CSP)
        self.assertNotIn("unsafe-inline", CSP)
        self.assertIn('<meta http-equiv="X-Content-Type-Options" content="nosniff">', out)
        self.assertIn('<meta name="referrer" content="strict-origin-when-cross-origin">', out)
        q = {"label": "Gold", "price": "$1", "day": 1.0, "month": 1.0, "series": [1, 2]}
        dial = stance_dial([q, {**q, "month": -1.0}])
        self.assertIn('class="needle n1of2"', dial)
        self.assertIn(".dial .needle.n1of2{--a:0deg}", CSS)
        self.assertNotRegex(out + dial, r'\sstyle="|<script>')  # CSP blocks inline style attributes and inline scripts

    def test_card_details(self):
        self.assertEqual(topic_of("Hot PPI shows the Fed's work is not done", ""), "Inflation")
        self.assertEqual(topic_of("U.S. budget deficit swells", "Treasury yields"), "Fiscal")
        self.assertEqual(topic_of("Celebrity buys yacht", "Big boat"), "Economy")
        self.assertEqual(source_name("https://www.cnbc.com/x.html"), "CNBC")
        self.assertEqual(source_name("https://example.org/x"), "example.org")
        self.assertEqual((read_minutes("word " * 10), read_minutes("word " * 231)), (1, 2))
        self.assertEqual(source_name("https://www.federalreserve.gov/x.htm"), "Federal Reserve")
        text = "U.S. prices rose 0.3% in September. Yields fell to 4.1%. Markets were calm."
        self.assertEqual(sentences(text, 2), "U.S. prices rose 0.3% in September. Yields fell to 4.1%.")
        self.assertEqual(sentences(text, 1), "U.S. prices rose 0.3% in September.")

    def test_closes_sparkline_and_ribbon(self):
        chart = {"chart": {"result": [{"indicators": {"quote": [{"close": [1.10, None, 1.12, 1.10]}]}}]}}
        self.assertEqual(closes(chart), [1.10, 1.12, 1.10])
        with self.assertRaises(ValueError):
            closes({"chart": {"result": [{"indicators": {"quote": [{"close": [None, 1.1]}]}}]}})
        svg = sparkline([1, 3, 2], width=80, height=24)
        self.assertIn('class="spark up"', svg)  # last >= first
        self.assertIn('d="M0.0,22.0 L40.0,2.0 L80.0,12.0"', svg)  # lowest value at the bottom, highest at the top
        self.assertIn('class="spark down"', sparkline([3, 1]))
        q = {"label": "Gold", "price": "$4,007.90", "day": -1.29, "month": 2.0, "series": [1, 2]}
        out = ribbon([q], "Oct 24, 06:00 UTC")
        self.assertIn('<span class="chg down">▼ 1.29%</span>', out)
        self.assertIn("1-month trend · as of Oct 24, 06:00 UTC", out)
        self.assertEqual(ribbon([], "x"), "")

    def test_stance_is_a_breadth_count(self):
        q = lambda m: {"month": m}  # noqa: E731
        self.assertEqual(stance([q(1), q(2), q(3), q(4), q(-1)]), (4, 5, "Broadly higher"))
        self.assertEqual(stance([q(1), q(-2), q(3), q(-4), q(-1)]), (2, 5, "Mixed"))
        self.assertEqual(stance([q(-1), q(-2), q(3), q(-4), q(-1)]), (1, 5, "Broadly lower"))

    def test_meta_and_tags(self):
        s = {"date": "2026-10-23T22:00:00+00:00", "minutes": 3}
        self.assertEqual(meta_line(s), '<p class="meta"><b>Global Desk</b> · '
                         '<time datetime="2026-10-23T22:00:00+00:00">Oct 23, 2026</time> · 3 min read</p>')
        self.assertEqual(tag("Central Banks"), '<span class="tag indigo">#POLICY</span>')
        self.assertEqual(topic_of("Crude oil tops $100 as OPEC trims output", ""), "Energy")

    def test_filters_and_key_points(self):
        self.assertEqual(filters_for("Central Banks"), ["policy"])
        self.assertEqual(filters_for("Energy"), ["commodities"])
        self.assertEqual(filters_for("Inflation"), [])  # shown under "All" only
        body = "Lead.\n\n## Key Data & Forecast\n- **CPI**: 3.5%\n- GDP 1%\n- Jobs 120k\n- Fourth"
        self.assertEqual(key_points(body), ["<strong>CPI</strong>: 3.5%", "GDP 1%", "Jobs 120k"])
        self.assertEqual(key_points("No bullets here."), [])

    def test_search_index_and_feed(self):
        s = {"slug": "2026-10-23-fed-holds-abc123", "title": 'Fed holds & "waits"', "topic": "Central Banks",
             "summary": "Rates held at 4%. Markets calm.", "date": "2026-10-23T22:00:00+00:00"}
        self.assertEqual(search_index([s]), [{"t": 'Fed holds & "waits"', "g": "#POLICY", "s": "Rates held at 4%.",
                                              "d": "Oct 23, 2026", "u": "articles/2026-10-23-fed-holds-abc123.html"}])
        feed = ET.fromstring(rss_feed([s], datetime(2026, 10, 24, 6, tzinfo=timezone.utc)))  # must be well-formed XML
        item = feed.find("channel/item")
        self.assertEqual(item.findtext("title"), 'Fed holds & "waits"')
        self.assertTrue(item.findtext("link").endswith("/articles/2026-10-23-fed-holds-abc123.html"))
        self.assertEqual(item.findtext("pubDate"), "Fri, 23 Oct 2026 22:00:00 +0000")


if __name__ == "__main__":
    unittest.main()
