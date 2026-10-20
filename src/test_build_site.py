import unittest

from build_site import markdown, parse_article

ARTICLE = """---
title: "Fed: \\"hold\\""
date: 2026-10-20T14:00:00+00:00
---

## Key Takeaway
- CPI **0.3%**
- <script>x</script>

See [CNBC](https://cnbc.test/a?b=1&c=2) or [bad](javascript:alert(1)).
"""


class BuildSiteTest(unittest.TestCase):
    def test_parse_and_render(self):
        meta, body = parse_article(ARTICLE)
        self.assertEqual(meta, {"title": 'Fed: "hold"', "date": "2026-10-20T14:00:00+00:00"})
        out = markdown(body)
        self.assertIn("<h2>Key Takeaway</h2>", out)
        self.assertIn("<ul><li>CPI <strong>0.3%</strong></li><li>&lt;script&gt;x&lt;/script&gt;</li></ul>", out)
        self.assertIn('<a href="https://cnbc.test/a?b=1&amp;c=2">CNBC</a>', out)
        self.assertNotIn('href="javascript', out)


if __name__ == "__main__":
    unittest.main()
