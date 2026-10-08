"""Fallos de red: un match o evento que falla no corta la corrida, y fetch reintenta lo transitorio."""

from urllib.error import HTTPError

import pytest

import vlr_pipeline.fetch as fetch
import vlr_pipeline.scraper as scraper


def http_error(code):
    return HTTPError("https://www.vlr.gg/1/x", code, "error", hdrs=None, fp=None)


def test_process_match_network_error_is_status_error(monkeypatch, tmp_path):
    def failing_soup_open(url=None, decode="iso-8859-1"):
        raise http_error(503)

    monkeypatch.setattr(scraper, "soup_open", failing_soup_open)
    monkeypatch.setattr(scraper.time, "sleep", lambda seconds: None)

    result = scraper.process_match("https://www.vlr.gg/1/x", folder=str(tmp_path))
    assert result["status"] == "error"
    assert "503" in result["error"]


def test_scrape_all_continues_after_event_failure(monkeypatch, tmp_path):
    scraped = []

    def fake_scrape_event(event_url, folder, encoding):
        if "roto" in event_url:
            raise http_error(503)
        scraped.append(event_url)
        return 2

    monkeypatch.setattr(scraper, "scrape_event", fake_scrape_event)
    events = [{"name": "roto", "url": "https://www.vlr.gg/event/roto"},
              {"name": "ok", "url": "https://www.vlr.gg/event/ok"}]

    assert scraper.scrape_all(events, folder=str(tmp_path)) == 3
    assert scraped == ["https://www.vlr.gg/event/ok"]


class FakePage:
    def __init__(self, html):
        self.html = html

    def read(self):
        return self.html.encode("iso-8859-1")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda seconds: None)


def test_soup_open_retries_transient_errors(monkeypatch, no_sleep):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(timeout)
        if len(calls) < 3:
            raise http_error(429)
        return FakePage("<title>ok</title>")

    monkeypatch.setattr(fetch, "urlopen", fake_urlopen)
    soup = fetch.soup_open("https://www.vlr.gg/1/x")
    assert soup.title.get_text() == "ok"
    assert calls == [fetch.TIMEOUT_SECONDS] * 3


def test_soup_open_does_not_retry_404(monkeypatch, no_sleep):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(timeout)
        raise http_error(404)

    monkeypatch.setattr(fetch, "urlopen", fake_urlopen)
    with pytest.raises(HTTPError):
        fetch.soup_open("https://www.vlr.gg/1/x")
    assert len(calls) == 1
