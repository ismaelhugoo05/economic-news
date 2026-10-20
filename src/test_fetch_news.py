import unittest

from fetch_news import is_macro, parse, to_markdown

RSS = b"""<rss><channel>
<item><title>Fed holds rates: &quot;wait and see&quot;</title><link>https://x.test/a</link>
<pubDate>Mon, 20 Oct 2026 14:00:00 GMT</pubDate><description>&lt;p&gt;CPI rose 0.3%.&lt;/p&gt;</description></item>
<item><title>Celebrity buys yacht</title><link>https://x.test/b</link><description>Big boat.</description></item>
<item><title>No link</title></item>
</channel></rss>"""


class FetchNewsTest(unittest.TestCase):
    def test_parse_filter_and_format(self):
        stories = list(parse(RSS, "Test"))
        self.assertEqual([s["url"] for s in stories], ["https://x.test/a", "https://x.test/b"])
        self.assertEqual(stories[0]["summary"], "CPI rose 0.3%.")
        self.assertEqual([is_macro(s) for s in stories], [True, False])
        md = to_markdown(stories[0])
        self.assertIn('title: "Fed holds rates: \\"wait and see\\""', md)
        self.assertIn('source_url: "https://x.test/a"', md)


if __name__ == "__main__":
    unittest.main()
