import unittest

from build_site import markdown, parse_article, read_minutes, source_name, topic_of

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


if __name__ == "__main__":
    unittest.main()
