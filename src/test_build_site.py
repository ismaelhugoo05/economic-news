import unittest
from datetime import date, datetime, timezone

from build_site import (
    coverage_series, markdown, parse_article, quote, read_minutes, sentences, source_name, ticker, topic_of,
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
        self.assertIn('<a href="https://cnbc.test/a?b=1&amp;c=2">CNBC</a>', out)
        self.assertNotIn('href="javascript', out)

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

    def test_quote_and_ticker(self):
        chart = {"chart": {"result": [{"indicators": {"quote": [{"close": [1.10, None, 1.12, 1.10]}]}}]}}
        price, change = quote(chart)
        self.assertEqual((price, round(change, 2)), (1.10, -1.79))
        inv_price, inv_change = quote(chart, invert=True)
        self.assertAlmostEqual(inv_price, 1 / 1.10)
        self.assertGreater(inv_change, 0)  # EUR falling means USD/EUR rising
        html_out = ticker([("Gold", "$4,007.90", -3.66), ("S&P 500", "7,623.68", 0.5)], "Oct 24, 06:00 UTC")
        self.assertIn('<span class="down">▼ 3.66%</span>', html_out)
        self.assertIn('<span class="up">▲ 0.50%</span>', html_out)
        self.assertIn("as of Oct 24, 06:00 UTC", html_out)
        self.assertEqual(ticker([], "x"), "")

    def test_coverage_series(self):
        at = lambda d: datetime(2026, 10, d, 12, tzinfo=timezone.utc)  # noqa: E731
        stories = [{"topic": "Inflation", "dt": at(23)}, {"topic": "Inflation", "dt": at(24)},
                   {"topic": "Trade", "dt": at(24)}, {"topic": "Fiscal", "dt": at(1)}, {"topic": "Trade", "dt": None}]
        series = coverage_series(stories, date(2026, 10, 24), days=3)
        self.assertEqual(series["days"], ["Oct 22", "Oct 23", "Oct 24"])
        self.assertEqual(series["series"], [{"name": "Inflation", "values": [0, 1, 1]}, {"name": "Trade", "values": [0, 0, 1]}])


if __name__ == "__main__":
    unittest.main()
