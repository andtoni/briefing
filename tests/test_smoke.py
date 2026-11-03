#!/usr/bin/env python3
"""Smoke test: build one whole edition from synthetic entries (tests/fixtures/synthetic_entries.json) to HTML, with no network and no model.

The feed reader, the direct feeds and GitHub Trending are stubbed, the editor is switched off (BRIEFING_EDITOR_MODEL empty), every outbound
request raises, and Kindle delivery is off. What remains is the real pipeline: cleaning, rules, sections, the front page, Contents and rendering.

    python3 tests/test_smoke.py               # build in a temporary folder and check it
    python3 tests/test_smoke.py --keep DIR    # also keep the edition in DIR (HTML, and the PDF and EPUB when Chromium and pandoc are installed)
"""
import datetime
import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOB = ROOT / "briefing"
FIXTURE = ROOT / "tests/fixtures/synthetic_entries.json"

try:
    import bs4  # noqa: F401
    import lxml  # noqa: F401
    import PIL  # noqa: F401
except ImportError:
    print("smoke test skipped: beautifulsoup4/lxml/Pillow not installed")
    sys.exit(0)

os.environ.update(BRIEFING_EDITOR_MODEL="", BRIEFING_TZ="UTC", BRIEFING_KINDLE_TO="", BRIEFING_FIRECRAWL_API_KEY="")
sys.path.insert(0, str(JOB))
import briefing  # noqa: E402


def entries(now):
    """The fixture's entries in the reader's shape, dated relative to `now`."""
    out = []
    for e in json.loads(FIXTURE.read_text())["entries"]:
        when = (now - datetime.timedelta(hours=e.pop("hours_ago"))).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
        out.append(dict(e, published=when, created_at=when))
    return out


def offline(*_a, **_k):
    raise AssertionError("the smoke test must not reach the network")


def build(out, keep_documents=False):
    """Run main() once against the fixture; return the edition's folder."""
    out = pathlib.Path(out)
    briefing.STATE, briefing.OUTPUT = out / "state", out / "editions"
    briefing.EDITIONS, briefing.WEEKLY_SEEN = briefing.STATE / "editions", briefing.STATE / "weekly_seen"
    briefing.KINDLE_SENT, briefing.KINDLE_FAILED = briefing.STATE / "kindle_sent", briefing.STATE / "kindle_failed"
    briefing.TRENDING_SEEN = briefing.STATE / "trending_seen"
    now = datetime.datetime.now(datetime.timezone.utc)
    briefing.fetch_reader = lambda since: entries(now)
    briefing.fetch_direct = lambda since: []
    briefing.fetch_forefront = lambda since, record=True: []
    briefing.fetch_trending = lambda day: []
    briefing.curl = offline
    briefing.resend_post = offline
    if not keep_documents:
        briefing.documents = lambda book, now, edition, pdf, epub: None
    argv = sys.argv
    sys.argv = ["briefing.py", "--since-hours", "24"]
    try:
        briefing.main()
    finally:
        sys.argv = argv
    folders = sorted(briefing.OUTPUT.iterdir())
    assert len(folders) == 1, folders
    return folders[0]


def check(folder):
    page = (folder / "briefing.html").read_text()
    soup = bs4.BeautifulSoup(page, "lxml")
    sections = [s["data-title"] for s in soup.select("section.sec")]
    titles = [a["data-title"] for a in soup.select("article")]
    assert soup.select_one("h1.masth").get_text() == "The Briefing", "the edition opens on its heading"
    assert soup.select_one("#toc") and soup.select("#toc a.titem"), "one Contents list"
    assert {"World", "Markets &amp; Macro", "Deals &amp; Investing", "Biotech &amp; Health", "AI", "Long reads"} <= {briefing.html.escape(s) for s in sections}, sections
    assert sections.index("World") < sections.index("Long reads"), "the themes, then Long reads"
    assert "Northwind Capital agrees to buy Lumen Tools for $2.4 billion" in titles and soup.find("section", attrs={"data-title": "Deals & Investing"}), "an acquisition is filed under Deals & Investing"
    assert "On patience in long-term investing" in titles, "a long single-author piece is a long read"
    assert "Verify your email address" not in page and "1 promotional or account mailing" in page, "admin mail is left out and counted"
    assert "Also today" in titles, "a short item becomes an Also today line"
    assert "%%BOOK%%" not in page and "<script" in page, "the reader page is complete and self-contained"
    return sections, titles


if __name__ == "__main__":
    if sys.argv[1:2] == ["--keep"]:
        target = pathlib.Path(sys.argv[2]).resolve()
        target.mkdir(parents=True, exist_ok=True)
        folder = build(target, keep_documents=True)
        print("sections:", ", ".join(check(folder)[0]))
        print(f"edition kept in {folder}")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            check(build(tmp))
    print("smoke test passed")
