import io
import json
import unittest
import urllib.error
from datetime import datetime, timezone

from fetch_news import article_text, gemini_error, gemini_text, is_macro, parse, parse_report, to_markdown, writer_prompt

RSS = b"""<rss><channel>
<item><title>Fed holds rates: &quot;wait and see&quot;</title><link>https://x.test/a</link>
<pubDate>Mon, 20 Oct 2026 14:00:00 GMT</pubDate><description>&lt;p&gt;CPI rose 0.3%.&lt;/p&gt;</description></item>
<item><title>Celebrity buys yacht</title><link>https://x.test/b</link><description>Big boat.</description></item>
<item><title>No link</title></item>
</channel></rss>"""

FILLER = " ".join(["analysis"] * 120)
REPORT = f"""# Rate Pause Leaves Markets Pricing a December Cut

The Federal Reserve held its benchmark rate at 4.25%-4.50%.

## Market Overview
{FILLER}

## Macroeconomic Implications
{FILLER}

## Key Data & Forecast
- Rate: 4.25%-4.50%
- {FILLER}
"""


class FetchNewsTest(unittest.TestCase):
    def test_parse_and_filter(self):
        stories = list(parse(RSS, "Test"))
        self.assertEqual([s["url"] for s in stories], ["https://x.test/a", "https://x.test/b"])
        self.assertEqual(stories[0]["summary"], "CPI rose 0.3%.")
        self.assertEqual([is_macro(s) for s in stories], [True, False])

    def test_parse_world_bank_records(self):
        xml = b"""<WbgNews>
<news><url>http://www.worldbank.org/a</url><title>Growth slows</title><descr>GDP to slow.</descr><lnchdt>2026-09-28T09:00:00Z</lnchdt></news>
<news><url>http://www.worldbank.org/b</url><title>Future page</title><lnchdt>2099-01-01T00:00:00Z</lnchdt></news>
</WbgNews>"""
        stories = list(parse(xml, "World Bank"))
        self.assertEqual([(s["url"], s["summary"]) for s in stories], [("http://www.worldbank.org/a", "GDP to slow.")])
        self.assertEqual(stories[0]["date"], datetime(2026, 9, 28, 9, tzinfo=timezone.utc))

    def test_article_text_keeps_body_paragraphs(self):
        page = "<nav><p>Menu</p></nav><p>The Bureau of Labor Statistics said prices rose <b>0.3%</b> in September.</p>"
        self.assertEqual(article_text(page), "The Bureau of Labor Statistics said prices rose 0.3% in September.")

    def test_report_to_markdown(self):
        headline, lead, body = parse_report(REPORT)
        self.assertEqual(headline, "Rate Pause Leaves Markets Pricing a December Cut")
        self.assertEqual(lead, "The Federal Reserve held its benchmark rate at 4.25%-4.50%.")
        s = {"url": "https://x.test/a", "source": "CNBC Economy", "date": datetime(2026, 10, 20, tzinfo=timezone.utc)}
        md = to_markdown(s, headline, lead, body)
        self.assertIn('title: "Rate Pause Leaves Markets Pricing a December Cut"', md)
        self.assertTrue(md.endswith("Reporting synthesized from [CNBC Economy](https://x.test/a) primary disclosures.\n"))
        with self.assertRaises(ValueError):
            parse_report("No headline here")

    def test_rejects_short_or_misstructured_reports(self):
        with self.assertRaisesRegex(ValueError, "words"):
            parse_report(REPORT.replace(FILLER, "short"))
        with self.assertRaisesRegex(ValueError, "headings"):
            parse_report(REPORT.replace("## Macroeconomic Implications", "## Macro Context"))

    def test_gemini_text(self):
        ok = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "plan", "thought": True}, {"text": "# Head"}, {"text": "line\n"}]}}]}
        self.assertEqual(gemini_text(ok), "# Headline\n")
        with self.assertRaises(ValueError):
            gemini_text({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]})
        with self.assertRaises(ValueError):
            gemini_text({"promptFeedback": {"blockReason": "SAFETY"}})

    def test_gemini_error_shows_quota_kind(self):
        body = json.dumps({"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "You exceeded your current quota.", "details": [
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
                {"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "21s"}]}}).encode()
        e = urllib.error.HTTPError("https://x.test", 429, "Too Many Requests", {}, io.BytesIO(body))
        self.assertEqual(gemini_error(e), "Gemini API error 429 RESOURCE_EXHAUSTED: You exceeded your current quota."
                         " | quota: GenerateRequestsPerMinutePerProjectPerModel-FreeTier | retry after 21s")
        plain = urllib.error.HTTPError("https://x.test", 503, "Unavailable", {}, io.BytesIO(b"upstream down"))
        self.assertEqual(gemini_error(plain), "Gemini API error 503: upstream down")

    def test_writer_prompt_uses_skill_rules(self):
        prompt = writer_prompt()
        self.assertIn("100% original", prompt)
        self.assertNotIn("name: economic-writer", prompt)
        self.assertIn("# <your headline>", prompt)


if __name__ == "__main__":
    unittest.main()
