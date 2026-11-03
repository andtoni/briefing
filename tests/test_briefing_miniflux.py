#!/usr/bin/env python3
"""Checks for the Briefing's Miniflux source: the entry shape, the excluded feeds, the per-feed cap, read-only paging, failure notices and the wiring."""
import datetime
import io
import json
import os
import pathlib
import sys
import tempfile
import time
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOB = ROOT / "briefing"
sys.path.insert(0, str(JOB))
import os  # noqa: E402
os.environ.setdefault("BRIEFING_TZ", "Africa/Johannesburg")  # the checks were written for a Cape Town reader: Morning before 11:00 local time
import miniflux as mf  # noqa: E402

UTC = datetime.timezone.utc
SINCE = datetime.datetime(2026, 10, 26, 3, 0, tzinfo=UTC)
TOKEN = "t" * 40
ENV = {"BRIEFING_MINIFLUX_TOKEN": TOKEN, "BRIEFING_MINIFLUX_URL": "https://miniflux.example"}
BODY = "<p>" + " ".join(f"Markets did something worth reading about today, number {i}." for i in range(60)) + "</p>"


def raw(i, title, created, published, feed="Noahpinion", category="Business", url=None, author="Noah Smith", feed_id=None, feed_url="https://www.noahpinion.blog/feed"):
    return {"id": i, "title": title, "author": author, "content": BODY, "url": url or f"https://example.org/p/{i}", "published_at": published, "created_at": created,
            "feed_id": feed_id, "feed": {"title": feed, "feed_url": feed_url, "category": {"title": category}}}


# entry shape
one = mf.entry(raw(7, " A title ", "2026-10-26T05:00:00.123456Z", "2026-10-26T07:30:00+02:00"))
assert one["id"] == mf.ID_BASE + 7 and one["feed_id"] is None and one["title"] == "A title" and one["author"] == "Noah Smith"
assert one["published"] == "2026-10-26T05:30:00.000000Z" and one["_source"] == "Noahpinion" and one["_section"] == "Business" and one["url"] == "https://example.org/p/7"
assert mf.entry(raw(8, "x", "2026-10-26T05:00:00Z", "", category="All"))["_section"] == "Other"
assert mf.entry(raw(8, "x", "2026-10-26T05:00:00Z", "", category="All"))["published"].startswith("2026-10-26T05:00:00")
assert mf.entry(raw(8, "x", "2026-10-26T07:00:00+02:00", "2026-10-26T07:00:00+02:00"))["created_at"] == "2026-10-26T05:00:00.000000Z", "created_at is UTC whatever offset Miniflux serves"
assert mf.entry(raw(9, "x", "", "")) is None, "an entry with no date at all cannot be placed in an edition"
assert mf.entry(raw(10, "x", "2026-10-26T05:00:00Z", "", feed_id=52))["feed_id"] == 52

# left out: an excluded category (Jobs, whatever its case) and the newsletter bridge's test address; any other newsletter stays
assert mf.entry(raw(11, "Role", "2026-10-26T05:00:00Z", "", feed="Job board", category="Jobs")) is None
assert mf.entry(raw(11, "Role", "2026-10-26T05:00:00Z", "", category=" jobs ")) is None
assert mf.entry(raw(12, "Your code", "2026-10-26T05:00:00Z", "", feed="test", category="Newsletters", feed_url="https://feeds.example/newsletters/test.xml")) is None
assert mf.entry(raw(13, "A letter", "2026-10-26T05:00:00Z", "", feed="someone", category="Newsletters", feed_url="https://feeds.example/newsletters/someone.xml"))["_section"] == "Newsletters"

# the per-feed cap: a back catalogue dated on arrival (many entries on one published second) is left out, and no feed gives more than PER_FEED
burst = [mf.entry(raw(100 + i, f"old {i}", "2026-10-26T07:51:49Z", "2026-10-26T07:51:48.95%04dZ" % i, feed="In the Pipeline", feed_id=11)) for i in range(mf.BURST)]
later = mf.entry(raw(200, "new post", "2026-10-26T19:09:54Z", "2026-10-26T19:09:53Z", feed="In the Pipeline", feed_id=11))
pair = [mf.entry(raw(300 + i, f"pair {i}", "2026-10-26T08:00:00Z", "2026-10-26T08:00:00Z", feed="Axios", feed_id=40)) for i in range(2)]
assert [x["title"] for x in mf.cap(burst + pair + [later])] == ["pair 0", "pair 1", "new post"], "the burst goes; two items in one poll are not a burst"
busy = [mf.entry(raw(400 + i, f"press {i}", "2026-10-26T08:00:00Z", f"2026-10-26T{i // 60:02d}:{i % 60:02d}:00Z", feed="FDA", feed_id=10)) for i in range(mf.PER_FEED + 5)]
kept = mf.cap(busy)
assert len(kept) == mf.PER_FEED == 25 and kept[0]["title"] == "press 5" and kept[-1]["title"] == f"press {mf.PER_FEED + 4}", "the newest PER_FEED, in order"

# paging asks for read and unread entries since the floor, newest last, and only ever reads
calls = []
pages = [{"entries": [raw(i, f"t{i}", "2026-10-26T04:00:00Z", "2026-10-26T04:00:00Z") for i in range(100)]},
         {"entries": [raw(100, "last", "2026-10-26T04:00:00Z", "2026-10-26T04:00:00Z")]}]


def get(base, token, path):
    calls.append((base, token, path))
    return pages[len(calls) - 1]


got = mf.entries("https://miniflux.example", TOKEN, SINCE - datetime.timedelta(days=2), get)
assert len(got) == 101 and len(calls) == 2
assert "offset=0" in calls[0][2] and "offset=100" in calls[1][2] and "status=unread&status=read" in calls[0][2] and "direction=asc" in calls[0][2]
assert f"published_after={int((SINCE - datetime.timedelta(days=2)).timestamp())}" in calls[0][2]

# a window larger than one run reads is a loud failure, not a silently truncated edition
full = {"entries": [raw(i, f"t{i}", "2026-10-26T04:00:00Z", "2026-10-26T04:00:00Z") for i in range(100)]}
_, notice = mf.fetch(SINCE, ENV, lambda b, t, p: full)
assert "more than 3000 entries" in notice and notice.startswith("Feeds unavailable")

# fetch: the window is entries created since the last edition; a feed's back catalogue is held back by the published floor; job and test feeds never come back
rows = {"entries": [
    raw(1, "fresh", "2026-10-26T04:00:00Z", "2026-10-26T03:30:00Z"),
    raw(2, "polled early", "2026-10-26T00:00:00Z", "2026-10-25T23:00:00Z"),
    raw(3, "old", "2026-10-24T01:00:00Z", "2026-10-24T00:00:00Z"),
    raw(4, "role", "2026-10-26T04:00:00Z", "2026-10-26T04:00:00Z", feed="Job board", category="Jobs"),
]}
inside, notice = mf.fetch(SINCE, ENV, lambda b, t, p: rows)
assert notice == "" and [x["title"] for x in inside] == ["fresh"]
# a feed added today: its back catalogue (about 100 posts of the last two days, each with its own date, all stored after the window opened) is left out; a post of the window
# and a newsletter that arrived a few hours late stay. No more than a few In the Pipeline items ever reach an edition.
backlog = {"entries": [raw(500 + i, f"old post {i}", "2026-10-26T07:51:49Z", (SINCE - datetime.timedelta(hours=13 + i * 0.35)).strftime("%Y-%m-%dT%H:%M:%SZ"), feed="In the Pipeline", feed_id=11) for i in range(100)]
           + [raw(700, "new post", "2026-10-26T19:09:54Z", "2026-10-26T19:09:53Z", feed="In the Pipeline", feed_id=11),
              raw(701, "late letter", "2026-10-26T04:00:00Z", "2026-10-26T00:30:00Z", feed="Axios", feed_id=40)]}
inside, _ = mf.fetch(SINCE, ENV, lambda b, t, p: {"entries": backlog["entries"][100:] if "offset=100" in p else backlog["entries"][:100]})
assert [x["title"] for x in inside] == ["new post", "late letter"], [x["title"] for x in inside][:5]
assert sum(x["_source"] == "In the Pipeline" for x in inside) <= 3 and not any(x["title"].startswith("old post") for x in inside)
_, notice = mf.fetch(SINCE, {}, lambda b, t, p: rows)
assert "token is not set" in notice
_, notice = mf.fetch(SINCE, {"BRIEFING_MINIFLUX_TOKEN": TOKEN}, lambda b, t, p: rows)
assert "BRIEFING_MINIFLUX_URL" in notice and notice.startswith("Feeds unavailable"), "no address, no default: the reader is yours to point at"
seen = []
mf.fetch(SINCE, {"BRIEFING_MINIFLUX_TOKEN": TOKEN, "BRIEFING_MINIFLUX_URL": "https://m.example/"}, lambda b, t, p: seen.append((b, t)) or {"entries": []})
assert seen == [("https://m.example/", TOKEN)]


def refuse(*a):
    raise mf.Unavailable("refused the API token, so it may need replacing")


inside, notice = mf.fetch(SINCE, ENV, refuse)
assert inside == [] and notice == "Feeds unavailable: Miniflux refused the API token, so it may need replacing." and TOKEN not in notice

# the HTTP layer: GET only, the token in a header, no retry on a refusal, three tries on a 5xx or a network error
class Reply(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


requests = []


def opener_for(*outcomes):
    queue = list(outcomes)

    def opener(req, timeout=None):
        requests.append(req)
        out = queue.pop(0)
        if isinstance(out, Exception):
            raise out
        return Reply(json.dumps(out).encode())
    return opener


time.sleep, real_sleep = (lambda s: None), time.sleep
try:
    ok = mf.api("https://m.example", TOKEN, "entries?limit=1", opener_for({"entries": []}))
    assert ok == {"entries": []} and requests[0].get_method() == "GET" and requests[0].get_header("X-auth-token") == TOKEN and requests[0].full_url == "https://m.example/v1/entries?limit=1"
    requests.clear()
    for status in (401, 403, 404):
        try:
            mf.api("https://m.example", TOKEN, "entries", opener_for(urllib.error.HTTPError("u", status, "x", {}, None)))
            raise AssertionError("must raise")
        except mf.Unavailable as e:
            assert len(requests) == 1 and TOKEN not in str(e)
        requests.clear()
    flaky = opener_for(urllib.error.HTTPError("u", 502, "x", {}, None), urllib.error.URLError("down"), {"entries": [1]})
    assert mf.api("https://m.example", TOKEN, "entries", flaky) == {"entries": [1]} and len(requests) == 3
    requests.clear()
    try:
        mf.api("https://m.example", TOKEN, "entries", opener_for(*[urllib.error.URLError("down")] * 3))
        raise AssertionError("must raise")
    except mf.Unavailable as e:
        assert "could not be reached" in str(e) and len(requests) == 3
finally:
    time.sleep = real_sleep
src = (JOB / "miniflux.py").read_text()
for word in ("POST", "PUT", "DELETE", "PATCH", "mark_as_read"):
    assert word not in src, f"miniflux.py must stay read-only: {word}"

# wiring in the Briefing
briefing_src = (JOB / "briefing.py").read_text()
main = briefing_src[briefing_src.index("def main():"):]
reader = briefing_src[briefing_src.index("def fetch_reader(since):"):briefing_src.index("def fetch_direct(since):")]
assert "fetch_reader(since)" in main and "MF.fetch(since,os.environ)" in reader
assert "if notice: raise SystemExit(notice)" in reader, "a failed Miniflux must not publish an edition without its feeds or move last_run"
assert TOKEN not in main + src

try:
    import bs4  # noqa: F401
    import lxml  # noqa: F401
    import PIL  # noqa: F401
except ImportError:
    print("briefing Miniflux checks passed (piece test skipped: beautifulsoup4/lxml/Pillow not installed)")
    sys.exit(0)
import briefing  # noqa: E402

essay = mf.entry(raw(1, "A long essay", "2026-10-26T04:00:00Z", "2026-10-26T03:30:00Z", feed="Stratechery by Ben Thompson"))
briefing.tidy_source(essay)
arts, promos, _, _ = briefing.build_articles([essay])
assert len(arts) == 1 and arts[0]["source"] == "Stratechery" and arts[0]["section"] == "Long reads" and arts[0]["words"] > 300 and arts[0]["url"] == "https://example.org/p/1"
os.environ["BRIEFING_MINIFLUX_TOKEN"] = TOKEN
assert "BRIEFING_MINIFLUX_TOKEN" not in briefing.editor_env(), "the editor model never sees the Miniflux token"
print("briefing Miniflux checks passed")
