from dart_digest.news_client import parse_google_news_rss


def test_parse_google_news_rss_extracts_items() -> None:
    sample = """<?xml version='1.0' encoding='UTF-8'?>
<rss><channel>
  <item>
    <title>삼성전자 관련 기사</title>
    <link>https://news.example.com/a</link>
    <pubDate>Fri, 27 Feb 2026 10:00:00 GMT</pubDate>
    <source url="https://news.example.com">예시뉴스</source>
  </item>
</channel></rss>"""

    items = parse_google_news_rss(sample)
    assert len(items) == 1
    assert items[0].title == "삼성전자 관련 기사"
    assert items[0].link == "https://news.example.com/a"
    assert items[0].source == "예시뉴스"
    assert items[0].published_at == "2026-02-27"
