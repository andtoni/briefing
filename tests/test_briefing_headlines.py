#!/usr/bin/env python3
"""Checks for the Briefing's themes and headlines: the theme mapping, pulling headlines out of roundup newsletters, ranking, the per-theme cap, the link to a piece of the
edition, repeats, and the whole thing through an edition build."""
import base64
import datetime
import json
import pathlib
import re
import sys
import tempfile
import types
import zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOB = ROOT / "briefing"
try:
    import bs4  # noqa: F401
    import lxml  # noqa: F401
except ImportError:
    print("briefing headline checks skipped: beautifulsoup4/lxml not installed")
    sys.exit(0)
sys.path.insert(0, str(JOB))
import os  # noqa: E402
os.environ.setdefault("BRIEFING_TZ", "Africa/Johannesburg")  # the checks were written for a Cape Town reader: Morning before 11:00 local time
import briefing  # noqa: E402
import headlines as H  # noqa: E402
import rules as R  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

# ------------------------------------------------------------------ themes
assert R.THEMES == ("World", "Markets & Macro", "Deals & Investing", "Biotech & Health", "AI")
for section, theme in (("World", "World"), ("Biopharma", "Biotech & Health"), ("Medicine & Science", "Biotech & Health"), ("Health AI", "Biotech & Health"), ("Health Policy", "Biotech & Health"),
                       ("Medtech", "Biotech & Health"), ("AI & Engineering", "AI"), ("Life", "Life"), ("Saved", "Saved"), ("Markets & Macro", "Markets & Macro")):
    assert R.theme_of(section, "Some Letter", "", "A headline") == theme, (section, theme)
assert R.theme_of("Business", "Some Letter", "", "Fed holds rates as inflation cools and bond yields fall") == "Markets & Macro"
assert R.theme_of("Business", "Some Letter", "", "KKR agrees a $6bn takeover of a hospital group in a private equity buyout") == "Deals & Investing"
assert R.theme_of("Business", "Some Letter", "", "A nuclear deal and a trade deal dominate the week") == "Markets & Macro", "a trade deal is not a deal"
assert R.theme_of("Business", "Some Letter", "", "Something with no signal at all") == "Markets & Macro", "Business with no signal is Markets & Macro"
assert R.theme_of("Other", "Some Letter", "", "Zepbound and the FDA") == "Biotech & Health" and R.theme_of("Other", "Some Letter", "", "Gardening tips") == "Other", "Other is filed by its words when they point anywhere"
assert R.theme_of("Other", "STAT", "STAT | D.C. Diagnosis", "Crackdowns loom") == "Biotech & Health" and R.theme_of("Business", "STAT+ The Readout", "STAT | The Readout", "Raises $50m") == "Biotech & Health", "STAT is Biotech & Health whatever its tag says"
assert R.classify("Nvidia unveils a new AI chip", "") == "AI" and R.classify("Ceasefire talks in Gaza stall", "") == "World" and R.classify("", "") == "" and R.classify("whatever", "World") == "World"
assert R.classify("A fund raises $200m in a Series B led by a venture firm", "Business") == "Deals & Investing"

# ------------------------------------------------------------------ links
b64 = lambda s: base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")
wsj = f"https://trk.wsj.com/click/48086590.1152698/{b64('https://www.wsj.com/articles/aocs-ambition-is-growing-8c2c7296?mod=djemwhatsnews')}/6ad330b305bb5d0c3301539dD404fa340"
assert H.untrack(wsj) == "https://www.wsj.com/articles/aocs-ambition-is-growing-8c2c7296", "the WSJ click tracker is decoded, its query dropped"
assert H.untrack(f"https://trk.wsj.com/click/1.2/{b64('http://pubads.g.doubleclick.net/gampad/clk?id=1')}/x") == "", "an advertisement is no link"
axios = f"https://link.axios.com/click/47985858.223215/{b64('https://www.axios.com/2026/10/23/trump-china-biotech?utm_source=newsletter&stream=top')}/abc"
assert H.untrack(axios) == "https://www.axios.com/2026/10/23/trump-china-biotech", "Axios uses the same tracker"
ftl = "l=" + "https%3A%2F%2Fwww.ft.com%2Fcontent%2F8948193b-438b-4d71-a0b1-31dff56fc308%3FsegmentId%3Dabc"
ft_link = "https://email.news-alerts.ft.com/c/" + base64.urlsafe_b64encode(zlib.compress(("category=newsletter&" + ftl + "&product=AutoEmail&r=reader%40example.com").encode())).decode().rstrip("=")
assert H.untrack(ft_link) == "https://www.ft.com/content/8948193b-438b-4d71-a0b1-31dff56fc308", "the FT email tracker carries the address in its l= parameter"
assert H.untrack("https://semafor.com/s/5p9fq8u7lu?email=reader@example.com") == "https://semafor.com/s/5p9fq8u7lu", "a publisher's own address loses its whole query: it may carry the reader's email"
assert H.untrack("https://example.org/a?utm_source=x&id=7&email=a@b.c") == "https://example.org/a?id=7", "elsewhere only tracking parameters go"
assert H.untrack("mailto:a@b.c") == "" and H.untrack("") == "" and H.opaque(H.untrack("https://trk.wsj.com/click/1.2/!!!/x")), "a tracker that cannot be decoded stays a tracker"
assert H.opaque("https://marketing.statnews.com/e3t/Ctc/LV+113/x") and H.opaque("https://click.e.economist.com/?qs=abc") and not H.opaque("https://www.ft.com/content/x")
assert H.story_key("https://www.ft.com/content/8948193b-438b-4d71-a0b1-31dff56fc308?x=1") == "ft:8948193b-438b-4d71-a0b1-31dff56fc308" and H.story_key("https://www.wsj.com/finance/stocks/the-earnings-boom-21decb53?mod=x") == "wsj:21decb53"
assert H.story_key("https://example.org/x") == "" and H.url_key("https://www.Example.org/a/b/?x=1#f") == "example.org/a/b"

# ------------------------------------------------------------------ pulling headlines out of the roundups (synthetic markup in each newsletter's layout)
def entry(**kw): return dict(dict(id=1, feed_id=1, title="T", author="", url="https://example.org/nl", published="2026-10-26T03:00:00.000000Z", _source="Example", _section="World", content=""), **kw)
para = lambda n: " ".join(f"Sentence {i} of the story about topic {n}." for i in range(14))
wsj_nl = entry(_source="WSJ What's News", author="WSJ What's News", title="AOC tempers her style", _section="Business", content=(
    f"<p>Plus, banks crack down on credit-card points junkies</p><p><a href='{wsj}'>AOC’s Ambition Is Growing—but Her Tactics Have Softened</a></p><p>NIC ANTAYA/BLOOMBERG</p>"
    f"<h3>1. Weighing a run for higher office, Rep. Alexandria Ocasio-Cortez broadens her outreach.</h3><p>{para(1)} <a href='https://trk.wsj.com/click/1.2/{b64('https://www.wsj.com/politics/elections/aoc-president-midterm-5d5d5d5d')}/h'>shifted tactics</a>—in ways that mattered.</p>"
    f"<h3>2. There’s a growing battle between card issuers and points junkies.</h3><p>{para(2)} <a href='https://trk.wsj.com/click/1.2/{b64('https://www.wsj.com/finance/banking/card-battle-77aa88bb')}/h'>banks push back</a>.</p>"
    f"<h3>3. Chipmakers.</h3><p>No link here at all and {para(3)}</p><p><a href='https://www.wsj.com/newsletters'>Newsletters & Alerts</a></p>"))
items = H.extract(H.kind_of(wsj_nl), briefing.prep(wsj_nl, sponsors=False)["html"], wsj_nl["url"], "Business", wsj_nl["published"])
assert [x["title"] for x in items] == ["AOC’s Ambition Is Growing—but Her Tactics Have Softened", "Weighing a run for higher office, Rep. Alexandria Ocasio-Cortez broadens her outreach",
                                       "There’s a growing battle between card issuers and points junkies"], [x["title"] for x in items]
assert items[0]["source"] == "The Wall Street Journal" and items[0]["hint"] == "Business" and items[0]["url"] == "https://www.wsj.com/articles/aocs-ambition-is-growing-8c2c7296", "WSJ: the lead link and the numbered sentences, trackers decoded, no navigation link, a heading without a link left out"
assert items[2]["url"] == "https://www.wsj.com/finance/banking/card-battle-77aa88bb" and items[1]["blurb"].startswith("Sentence 0") and items[0]["pos"] == 0 and items[2]["pos"] == 2

ftb = entry(_source="FT newsletters (Briefing)", author="FT Briefing", title="Markets afternoon briefing: Oil", _section="Business", content=(
    "<p>The markets news you need</p><p><a href='https://email.news-alerts.ft.com/c/x'>All newsletters</a> | <a href='https://ep.ft.com/x'>Read in browser</a></p><h2>Markets</h2>"
    + "".join(f"<p><a href='{u}'>{t}</a></p><p>{b}</p>" for u, t, b in ((ft_link, "Oil hits $116 for first time since April as global stocks knocked by AI fears", "Markets face twin threats"),
                                                                         ("https://www.ft.com/content/5a6e15e9-249d-4d59-a140-c51302930a9f?segmentId=1", "Gold drops below $4,000 as haven asset joins sell-off", "Price has plunged")))))
items = H.extract(H.kind_of(ftb), briefing.prep(ftb, sponsors=False)["html"], ftb["url"])
assert [(x["title"], x["url"], x["source"]) for x in items] == [("Oil hits $116 for first time since April as global stocks knocked by AI fears", "https://www.ft.com/content/8948193b-438b-4d71-a0b1-31dff56fc308", "Financial Times"),
                                                                 ("Gold drops below $4,000 as haven asset joins sell-off", "https://www.ft.com/content/5a6e15e9-249d-4d59-a140-c51302930a9f", "Financial Times")], items
assert items[0]["blurb"] == "Markets face twin threats"

firstft = entry(_source="FT newsletters", author="FirstFT Americas", title="AI boom or bust?", _section="Business", content=(
    "<p>Good morning. In today’s newsletter:</p><ul><li><p>AI-linked sell-off fuels bubble debate</p></li><li><p>Start-up promises genetically enhanced working dogs</p></li></ul>"
    f"<p><strong>A brutal tech sell-off spread to Asia on Friday,</strong> as concerns grow. {para(1)}</p><p>Shares in Meta <a href='https://www.ft.com/content/6e318b81-a771-4842-9754-e265fef2852f'>tumbled 7 per cent</a> yesterday after the results.</p>"
    "<h3>Five more top stories</h3>"
    f"<p><strong>1. Exclusive: The US is preparing for a protracted conflict with Iran,</strong> Donald Trump’s ambassador said. Bombing campaigns and <a href='https://www.ft.com/content/70379a26-c20e-4501-aec9-a9a0089cdd3d'>sanctions</a> will follow, officials add.</p>"
    "<ul><li><strong>Oil hits $114 a barrel:</strong> Brent crude extended a <a href='https://www.ft.com/content/8948193b-438b-4d71-a0b1-31dff56fc308'>blistering rally</a> on Friday amid fears of escalation.</li></ul>"
    f"<p>Ordinary paragraph that mentions a <a href='https://www.ft.com/content/aaaaaaaa-0000-0000-0000-000000000000'>story</a> in passing and goes on for a good while longer.</p>"))
items = H.extract(H.kind_of(firstft), briefing.prep(firstft, sponsors=False)["html"], firstft["url"])
assert [x["title"] for x in items] == ["AI-linked sell-off fuels bubble debate", "Exclusive: The US is preparing for a protracted conflict with Iran", "Oil hits $114 a barrel"], [x["title"] for x in items]
assert items[0]["url"].endswith("6e318b81-a771-4842-9754-e265fef2852f") and items[2]["url"].endswith("8948193b-438b-4d71-a0b1-31dff56fc308"), "FirstFT: the lead is the first item of the list that follows the introduction; then the numbered and bold-led items only"

sem = entry(_source="Semafor Flagship", author="Semafor Flagship", title="Underground anger", _section="World", content=(
    "<ol><li>US warns of Iran threats</li><li>AI’s missing corporate gains</li></ol><p>A look at the week ahead.</p>"
    f"<h2>1 · New threats push US and Iran toward war</h2><p><strong>The US director of national intelligence warned that Iran was in the <a href='https://semafor.com/s/5p9fq8u7lu?email=a@b.c'>advanced stages</a> of planning.</strong> {para(1)}</p>"
    f"<h2>2 · Hunting for AI gains outside Mag 7</h2><p>{para(2)} <a href='https://semafor.com/s/8aj00ofu04?email=a@b.c'>report</a></p>"))
items = H.extract(H.kind_of(sem), briefing.prep(sem, sponsors=False)["html"], sem["url"])
assert [(x["title"], x["url"]) for x in items] == [("New threats push US and Iran toward war", "https://semafor.com/s/5p9fq8u7lu"), ("Hunting for AI gains outside Mag 7", "https://semafor.com/s/8aj00ofu04")], items

eco = entry(_source="The Economist", author="The Economist", title="The World in Brief: Iran", _section="World", content=(
    "<h2>Today’s top stories</h2><p class='brief'>▸ <b>America’s</b> top intelligence official said that <b>Iran</b> had drawn up plans to kill Americans. In a leaked memo, Jay Clayton claimed that the plotting had reached advanced stages.</p>"
    "<p class='brief'>▸ Meanwhile, <b>Mr Trump</b> will exempt more <b>Canadian</b> products from his tariffs, said <a href='https://click.e.economist.com/?qs=abc'>Susan Collins</a> , a senator. Levies will go.</p>"))
items = H.extract(H.kind_of(eco), briefing.prep(eco, sponsors=False)["html"], "https://www.economist.com/the-world-in-brief")
assert [x["title"] for x in items] == ["America’s top intelligence official said that Iran had drawn up plans to kill Americans", "Mr Trump will exempt more Canadian products from his tariffs, said Susan Collins, a senator"], [x["title"] for x in items]
assert items[0]["url"] == "https://www.economist.com/the-world-in-brief" and H.opaque(items[1]["url"]) and items[1]["title"].startswith("Mr Trump will exempt") and items[1]["source"] == "The Economist", "an Economist brief: its first sentence is the headline, linked where it links and otherwise to the brief"

axios_nl = entry(_source="Axios Pro Rata", author="Dan Primack", title="Axios Pro Rata: Biotech bomb", _section="Business", content=(
    f"<p>Intro without any link and nothing to report at all, only a long run of words to pass the length bar.</p>"
    f"<p><strong>Nouscom,</strong> a Swiss immunotherapy developer, raised €120m in Series D funding from investors. <a href='{axios}'>Details</a></p>"))
items = H.extract(H.kind_of(axios_nl), briefing.prep(axios_nl, sponsors=False)["html"], axios_nl["url"])
assert len(items) == 1 and items[0]["title"].startswith("Nouscom, a Swiss immunotherapy developer, raised €120m in Series D funding") and items[0]["source"] == "Axios" and items[0]["url"].endswith("trump-china-biotech")

def stat_nl(series, body, source="Pharmalittle + Health Tech (STAT+)"): return entry(_source=source, author=f"STAT | {series}", title="STAT list", _section="Biopharma", content=body)
stat_list = stat_nl("Daily Recap", "".join(f"<h2><a href='https://marketing.statnews.com/e3t/Ctc/LV+113/x{n}'>STAT+ | {t}</a></h2><h2>By Reporter {n}</h2><p>{para(n)}</p>" for n, t in enumerate(("Patient dies in Bristol Myers Squibb autoimmune CAR-T trial", "Diabetes association says threat preceded ejections")))
                    + "<p>Short.</p>")
items = H.extract(H.kind_of(stat_list), briefing.prep(stat_list, sponsors=False)["html"], "")
assert [x["title"] for x in items] == ["Patient dies in Bristol Myers Squibb autoimmune CAR-T trial", "Diabetes association says threat preceded ejections"] and all(x["source"] == "STAT" and H.opaque(x["url"]) for x in items), "STAT lists: the heading text without the STAT+ tag, the byline line left out"
pl = stat_nl("Pharmalittle", f"<p>And so, another working week will soon draw to a close. Not a moment too soon, yes?</p><p>A large trial of a personalised mRNA vaccine cut the risk of recurrence in melanoma by 42%, STAT tells us. Reuters has <a href='https://marketing.statnews.com/e3t/Ctc/LV+113/p1'>the report</a> in full today.</p>", source="STAT+ | Pharmalittle")
pl["author"] = "STAT+ | Pharmalittle"
items = H.extract(H.kind_of(pl), briefing.prep(pl, sponsors=False)["html"], "")
assert len(items) == 1 and items[0]["title"].startswith("A large trial of a personalised mRNA vaccine cut the risk of recurrence in melanoma by 42%"), "Pharmalittle has no headings: its link paragraphs are the items"
assert H.kind_of(entry(_source="Stratechery", author="Ben Thompson", title="An essay")) is None and H.kind_of(entry(_source="FT newsletters", author="FT Unhedged", title="Unhedged: Bonds")) is None, "written newsletters are not roundups"
assert H.kind_of(entry(_source="STAT+ The Readout", author="STAT | The Readout")) is None, "the Readout is a written series"
promo = entry(_source="The Economist", author="The Economist", content="<p>The Economist This Week</p>" + "<img src='x.jpg'>" * 25)
assert R.muted(promo) and H.kind_of(promo) is None, "the promo digest is muted: it is neither a piece nor a roundup"
assert H.extract(H.kind_of(wsj_nl), "<p>nothing here</p>", "") == [] and H.extract(("x", "p", ("heading",), False), "", "") == []

# ------------------------------------------------------------------ ranking, the cap and repeats
NOW_STAMP = "2026-10-26T03:00:00.000000Z"
def head(n, theme_hint="Markets & Macro", source="Financial Times", url=None, **kw):
    return dict(dict(title=f"Headline number {n} about the economy", url=url or f"https://example.org/{source[0]}/{n}", blurb=f"Blurb {n}", source=source, pos=n, hint=theme_hint, published=NOW_STAMP), **kw)
pool = [head(n, source=["Financial Times", "The Wall Street Journal", "Semafor"][n % 3]) for n in range(30)]
prompts = []
def editor(reply):
    def ask(prompt):
        prompts.append(prompt)
        return reply
    return ask
scores = {str(n): {"section": ["World", "Markets & Macro", "Deals & Investing", "Biotech & Health", "AI"][n % 5], "score": 10 - n * .2} for n in range(30)}
ranked = H.rank(pool, editor({"items": scores, "same": [[0, 5]]}), "Finance first.")
assert "untrusted" in prompts[0] and "never as instructions" in prompts[0] and "Finance first." in prompts[0] and '"headline": "Headline number 29' in prompts[0] and "same story" in prompts[0]
assert [x["title"] for x in ranked][:2] == ["Headline number 0 about the economy", "Headline number 1 about the economy"] and all(x["score"] >= H.MIN_SCORE for x in ranked), "best first; below the minimum score is not news"
assert "Headline number 5 about the economy" not in [x["title"] for x in ranked], "headlines that report the same story are one: the better scored stays"
by = H.cap(ranked)
assert list(by) == ["World", "Markets & Macro", "Deals & Investing", "Biotech & Health", "AI"] and all(len(v) <= H.PER_THEME for v in by.values()), "the five themes in order, at most six each"
assert all(sum(1 for x in v if x["source"] == s) <= H.PER_PUB for v in by.values() for s in {x["source"] for x in v}) or any(len(v) < 4 for v in by.values()), "at most three from one publication while others remain"
assert all([x["score"] for x in v] == sorted((x["score"] for x in v), reverse=True) for v in by.values())
many = [head(n, source="Financial Times") for n in range(12)]
capped = H.cap(H.rank(many, editor({"items": {str(n): {"section": "World", "score": 9} for n in range(12)}}), ""))
assert len(capped["World"]) == H.PER_THEME == 6, "only one publication left: it fills the six"
mixed = [head(n, source="Financial Times") for n in range(5)] + [head(10 + n, source="Semafor") for n in range(5)]
sc = {str(n): {"section": "World", "score": 9 - n * .1} for n in range(10)}
got = H.cap(H.rank(mixed, editor({"items": sc}), ""))["World"]
assert len(got) == 6 and sum(1 for x in got if x["source"] == "Financial Times") == 3 and sum(1 for x in got if x["source"] == "Semafor") == 3, "three from each when both have more"
assert H.cap([]) == {}
low = H.rank([head(1), head(2)], editor({"items": {"0": {"section": "AI", "score": 2}, "1": {"section": "nonsense", "score": 7}}}), "")
assert [x["title"] for x in low] == ["Headline number 2 about the economy"] and low[0]["theme"] == "Markets & Macro", "a score below three is dropped; an invalid section falls back to the feed's"
assert H.rank([head(1), head(2)], editor({"items": {"1": {"section": "AI", "score": True}}}), "")[0]["score"] >= 0 and len(H.rank([head(1), head(2)], editor({"items": {}}), "")) == 2
fallback = H.rank([head(n, hint) for n, hint in enumerate(("World", "Business", "AI"))], editor(None), "")
assert [x["theme"] for x in fallback] == ["World", "Markets & Macro", "AI"] and fallback[0]["score"] > fallback[1]["score"] > fallback[2]["score"] or fallback[0]["pos"] == 0, "no editor: the mailing's own order and tag"
assert H.rank([head(1)], None, "") and H.rank([], editor({}), "") == []
assert len(H.unique([head(1), head(1, url="https://example.org/other"), head(2, url="https://example.org/F/1"), head(3)])) == 2, "the same title or the same address is one headline"

# Following a tracker: only the Economist's host is ever requested; STAT's is matched by headline to its own feed with no request.
asked = []
hops = {"https://click.e.economist.com/?qs=a": "https://www.economist.com/europe/2026/10/22/a-story?utm_source=x",
        "https://click.e.economist.com/?qs=b": "https://evil.example.net/x",
        "https://click.e.economist.com/?qs=c": "https://click.e.economist.com/?qs=c2", "https://click.e.economist.com/?qs=c2": "https://www.economist.com/account/preferences",
        "https://click.e.economist.com/?qs=d": "https://click.e.economist.com/?qs=d2", "https://click.e.economist.com/?qs=d2": "https://click.e.economist.com/?qs=d3",
        "https://click.e.economist.com/?qs=d3": "https://click.e.economist.com/?qs=d4", "https://click.e.economist.com/?qs=d4": "https://www.economist.com/x/late"}
def fake_curl(url, *args):
    asked.append(url); assert "-L" not in args and "%{redirect_url}" in args, "one hop at a time, the redirect is never followed"
    return hops.get(url, "")
stat_feed = [dict(title="Patient dies in Bristol Myers Squibb autoimmune CAR-T trial", url="https://www.statnews.com/2026/10/25/patient-dies-bms/")]
tracked = [dict(head(1), url="https://click.e.economist.com/?qs=a"), dict(head(2), url="https://click.e.economist.com/?qs=b"), dict(head(3), url="https://click.e.economist.com/?qs=unsubscribe"),
           dict(head(4), url="https://marketing.statnews.com/e3t/Ctc/LV+113/x", title="Patient dies in Bristol Myers Squibb autoimmune CAR-T trial!"), dict(head(5), url="https://marketing.statnews.com/e3t/Ctc/LV+113/y"),
           dict(head(6), url="https://link.axios.com/click/1/x"), dict(head(7), url="https://email.evil.example/c/unsub?x=1"), dict(head(8), url="https://click.e.economist.com/?qs=c"),
           dict(head(9), url="https://click.e.economist.com/?qs=d")]
before = [x["url"] for x in tracked]
H.resolve(tracked, fake_curl, lambda _s: None, stat_feed)
assert [x["url"] for x in tracked] == ["https://www.economist.com/europe/2026/10/22/a-story", before[1], before[2], "https://www.statnews.com/2026/10/25/patient-dies-bms/", before[4], before[5], before[6], before[7], before[8]], [x["url"] for x in tracked]
assert asked == ["https://click.e.economist.com/?qs=a", "https://click.e.economist.com/?qs=b", "https://click.e.economist.com/?qs=c", "https://click.e.economist.com/?qs=c2"] + ["https://click.e.economist.com/?qs=d", "https://click.e.economist.com/?qs=d2", "https://click.e.economist.com/?qs=d3"], asked
assert "https://www.economist.com/account/preferences" not in asked and "https://evil.example.net/x" not in asked, "only the tracker's own host is ever requested, never an address that looks like unsubscribe or preferences, never at most three hops"

recs = [dict(headlines=[dict(title="Old headline already shown here", url="https://example.org/old"), "junk"]), dict(pieces=[])]
left = H.drop_repeats([head(1, url="https://example.org/old?utm_source=x"), dict(head(2), title="Old headline already shown here!"), head(3)], recs)
assert [x["title"] for x in left] == ["Headline number 3 about the economy"], "a headline an earlier edition listed does not come back, by address or by title"

# ------------------------------------------------------------------ link to the piece in the edition
piece = lambda **kw: dict(dict(title="A piece", url="", source="Paper", section="World", words=300, mins=2, html="<p>x</p>", author=""), **kw)
pieces = [piece(title="Mercuria in court after Hormuz losses", url="https://www.ft.com/content/eedb7159-65df-45de-91f9-fde8de99e61c", i=3),
          piece(title="Two AI chipmakers make up a third of the earnings boom", url="https://www.wsj.com/finance/stocks/the-earnings-boom-21decb53", i=4),
          piece(title="Unrelated essay", url="https://example.org/essay", i=5), piece(title="A brief", brief=True, url="https://example.org/brief", i=6)]
lines = [dict(head(1), url="https://www.ft.com/content/eedb7159-65df-45de-91f9-fde8de99e61c?segmentId=1", title="Mercuria challenges court"),
         dict(head(2), url="https://www.wsj.com/finance/stocks/something-else-entirely-21decb53?mod=x", title="Another title entirely"),
         dict(head(3), url="https://example.org/tracker/9", title="Unrelated essay"),
         dict(head(4), url="https://example.org/brief", title="Nothing like it"),
         dict(head(5), url="https://example.org/none", title="Nothing at all like any piece")]
H.link_pieces(lines, pieces)
assert [x.get("to", {}).get("i") for x in lines] == [3, 4, 5, None, None], "by the FT content id, the WSJ article hash, then the title; a brief is not a story"
rows = H.lines_html(lines[:1] + lines[4:], lambda p: f"a{p['i']}")
assert "<a href='#a3' data-go='a3'>Mercuria challenges court</a> — <b>Financial Times</b>" in rows and "<a href='https://example.org/none' target='_blank' rel='noopener'>Nothing at all like any piece</a> — <b>Financial Times</b>" in rows, rows
assert rows.startswith("<p class='follow'>") and rows.count("<p class='follow'>") == 2 and "xsub" not in rows, "the headline list has no sub-heading of its own"
assert H.lines_html(lines[:1], lambda p: "a3", "Also today").startswith("<h2 class='xsub'>Also today</h2>")
lp = H.list_piece("World", lines[:2], "2026-10-26")
assert lp["section"] == "World" and lp["title"] == "Headlines" and lp["source"] == "Financial Times" and lp["n"] == 2 and lp["unit"] == ("headline", "headlines") and len(lp["lines"]) == 2

# ------------------------------------------------------------------ through the edition: newsletters, then articles, then Also today; one Contents list; no cover
now = datetime.datetime(2026, 10, 26, 7, 15, tzinfo=briefing.TZ)
full = lambda theme, title, url, **kw: dict(dict(id=hash(title) % 10 ** 6, title=title, source="The Wall Street Journal", section=theme, author="Jane Doe", date="2026-10-26", words=600, mins=3, html="<p>" + "word " * 100 + "</p>", url=url, fulltext=True), **kw)
art_ft = full("Markets & Macro", "Mercuria in court after Hormuz losses", "https://www.ft.com/content/eedb7159-65df-45de-91f9-fde8de99e61c", source="Financial Times", score=8, summary="Mercuria is in court. Its losses came from Hormuz.")
art_w = full("World", "A world story in full", "https://www.wsj.com/world/a-world-story-12345678", score=6)
brief_w = dict(full("World", "The world in brief: Lula wins", "https://www.economist.com/the-world-in-brief", source="The Economist · World in Brief", score=1, fulltext=False), daily=True, author_raw="The Economist")
arts_, lists_ = briefing.compose([art_ft, art_w, brief_w], [dict(title="Oil climbs as Gulf tensions rise", url="https://example.org/oil", source="FT Alphaville", author="", section="Markets & Macro")], log=lambda m: None)
overflow = briefing.also_today(lists_, "2026-10-26")
page, total, book = briefing.render([*arts_, *overflow], [], now, "Morning", ["Example full text unavailable: the plug-in could not read it."])
soup = BeautifulSoup(book, "lxml")
titles = [(briefing.html.unescape(a.find_previous("section", class_="sec")["data-title"]), a["data-title"]) for a in soup.select("article")]
assert titles == [("World", "The world in brief: Lula wins"), ("World", "A world story in full"), ("Markets & Macro", "Mercuria in court after Hormuz losses"), ("Markets & Macro", "Also today")], titles
assert 'id="cover"' not in book and "cv-" not in book and book.index('class="masth">The Briefing<') < book.index('id="toc"'), "no cover: the edition opens on a plain heading"
assert "Headlines" not in book and all(t.find_parent(id="toc") or t.find_parent("article", class_="lines") or t.find_parent(class_="endnav") for t in soup.find_all(string=re.compile("Also today"))), "Also today only at the end of a section"
also = soup.select_one("article.lines")
assert "compact" in also["class"] and also.select("p.follow b")[0].get_text() == "FT Alphaville" and also.select_one("h2.xsub").get_text() == "Also today"
for a in soup.select("article:not(.lines)"):
    assert a.select_one(".by b"), f"a bold publisher on every byline: {a['data-title']}"
assert soup.select_one("article#a1 .by").decode_contents().startswith("<b>The Wall Street Journal</b> · Jane Doe"), "the publisher in bold, then the journalist"
toc = soup.select_one("#toc")
assert [x.select_one("span").get_text() for x in toc.select("a.tsec")] == ["World", "Markets & Macro"] and len(toc.select("a.titem")) == 4 and all(x.select_one(".tm b") for x in toc.select("a.titem")), "one Contents list: each section, its items under it, the publisher in bold"
b = BeautifulSoup(book, "lxml"); briefing.kindle_structure(b); briefing.kindle_markup(b)
epub_html = str(b)
assert b.body.find_all("h1") == [b.body.find("h1", class_="title")] and [h.get_text() for h in b.select("h2.section")] == ["World", "Markets & Macro"] and len(b.select("h3.story")) == 4, "one chapter: sections as h2, stories as h3"
assert "Also today" in epub_html

# ------------------------------------------------------------------ the whole pipeline: roundups to lists, with the editor stubbed
class Clock(datetime.datetime):
    at = datetime.datetime(2026, 10, 26, 2, 30, tzinfo=datetime.timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.at.astimezone(tz) if tz else cls.at

real = {k: getattr(briefing, k) for k in ("datetime", "STATE", "OUTPUT", "KINDLE_SENT", "KINDLE_FAILED", "TRENDING_SEEN", "EDITIONS", "WEEKLY_SEEN",
                                          "RESEND_KEY", "fetch_reader", "fetch_direct", "fetch_forefront", "fetch_fulltext", "fill_full_text", "ask_editor", "ask_model", "fetch_trending",
                                          "documents", "send_kindle", "add_summaries")}
with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    asked = []
    def ask_model(prompt):
        asked.append(prompt)
        if "rank the headlines" in prompt:
            lines_ = [json.loads(x) for x in prompt.split("HEADLINES, one JSON object per line\n", 1)[1].split("\n\nFor every headline", 1)[0].split("\n")]
            theme = lambda t: "Markets & Macro" if re.search(r"Mercuria|Oil|stocks|Gold", t) else "World"
            return {"items": {str(l["id"]): {"section": theme(l["headline"]), "score": 8} for l in lines_}, "same": []}
        return None
    briefing.datetime = types.SimpleNamespace(datetime=Clock, timezone=datetime.timezone, timedelta=datetime.timedelta, date=datetime.date)
    briefing.STATE, briefing.OUTPUT = tmp / "state", tmp / "public"
    briefing.KINDLE_SENT, briefing.KINDLE_FAILED = briefing.STATE / "kindle_sent", briefing.STATE / "kindle_failed"
    briefing.TRENDING_SEEN = briefing.STATE / "trending_seen"
    briefing.EDITIONS, briefing.WEEKLY_SEEN = briefing.STATE / "editions", briefing.STATE / "weekly_seen"
    briefing.OUTPUT.mkdir(parents=True); briefing.RESEND_KEY = ""
    nl = dict(wsj_nl, id=11, _section="Business")
    full_ft = dict(entry(id=12, title="Mercuria challenges the Baltic Exchange in court", url="https://www.ft.com/content/eedb7159-65df-45de-91f9-fde8de99e61c", _source="Financial Times", _section="Markets & Macro",
                         author="Jane Roe", _fulltext="ft:eedb7159-65df-45de-91f9-fde8de99e61c", content="".join(f"<p>Paragraph {n}: " + " ".join(f"fact {n}.{i}" for i in range(60)) + "</p>" for n in range(30))))
    ftbrief = dict(ftb, id=13, content=ftb["content"].replace("Oil hits $116", "Mercuria challenging the court after Hormuz").replace("https://email.news-alerts.ft.com/c/eJ", "x"))
    ftbrief["content"] = ftb["content"] + f"<p><a href='https://www.ft.com/content/eedb7159-65df-45de-91f9-fde8de99e61c?x=1'>Mercuria challenges the Baltic Exchange in court</a></p><p>The case will test the exchange.</p>"
    sem_nl = dict(sem, id=14)
    essay = entry(id=15, title="Money Stuff: A long essay", _source="Money Stuff", author="Matt Levine", _section="Business", url="https://example.org/money-stuff",
                  content="".join(f"<p>Essay paragraph {n}: " + " ".join(f"point {n}.{i}" for i in range(80)) + "</p>" for n in range(30)))
    result = briefing.FT.Result([full_ft], ["Example full text unavailable: the plug-in could not read it."], ["ft:eedb7159-65df-45de-91f9-fde8de99e61c"], {"example": "1 read"}, [])
    briefing.fetch_reader = lambda since: [nl, ftbrief, sem_nl, essay]
    briefing.fetch_direct = lambda since: []; briefing.fetch_forefront = lambda since, record=True: []
    briefing.fetch_fulltext = lambda since, entries, utc, now, edition: result
    briefing.fill_full_text = lambda entries: None; briefing.ask_editor = lambda arts, shown=(): {"must": [i for i, a in enumerate(arts) if a["title"].startswith("Mercuria")][:1], "score": {str(i): 5 for i in range(len(arts))}}
    briefing.ask_model = ask_model; briefing.fetch_trending = lambda day: []
    briefing.documents = lambda book, now, edition, pdf, epub: epub.write_bytes(b"epub"); briefing.send_kindle = lambda *a: None
    briefing.add_summaries = lambda arts: arts
    sys.argv = ["briefing.py", "--since-hours", "24"]
    try:
        briefing.main()
        page = (briefing.OUTPUT / "briefing-2026-10-26-am/briefing.html").read_text()
        soup = BeautifulSoup(page, "lxml")
        titles = [(briefing.html.unescape(a.find_previous("section", class_="sec")["data-title"]), a["data-title"]) for a in soup.select("article")]
        secs_ = [s_ for s_, _ in titles]
        assert secs_.index("World") < secs_.index("Markets & Macro") < secs_.index("Long reads"), titles
        assert ("Long reads", "A long essay") in titles and ("Markets & Macro", "Mercuria challenges the Baltic Exchange in court") in titles, titles
        macro = [t for s_, t in titles if s_ == "Markets & Macro"]
        assert macro[-1] == "Mercuria challenges the Baltic Exchange in court" or macro[-1] == "Also today", "the newsletters before the full article"
        world = [a for a in soup.select("article") if a.find_previous("section", class_="sec")["data-title"] == "World" and a["data-title"] != "Also today"]
        assert world and all(w.select_one(".by b") for w in world), "the World newsletters are printed whole with their publisher"
        assert [w["data-title"] for w in world] == ["Underground anger"] and ("World", "Also today") in titles, "Semafor Flagship prints; What's News, not in the stack, is an Also today line"
        assert "Must read" in page
        assert "Example full text unavailable: the plug-in could not read it." in page
        record = json.loads(next((briefing.STATE / "editions").glob("*.json")).read_text())
        assert record["headlines"] and all(set(h) == {"title", "url", "source"} for h in record["headlines"]) and any(h["source"] == "Semafor" for h in record["headlines"]), "the headlines shown are recorded for the no-repeat rule"
        assert [p["title"] for p in record["pieces"] if p["title"] == "Also today"] == [], "the lists are not pieces"
        assert any("rank the headlines" in p for p in asked), "one editor run ranks the headlines"
        # Next edition: the same roundups again. Nothing new, nothing published; with one new headline, only that one is listed.
        Clock.at = datetime.datetime(2026, 10, 26, 10, 30, tzinfo=datetime.timezone.utc)
        briefing.fetch_fulltext = lambda since, entries, utc, now, edition: briefing.FT.Result([], [], [], {}, [])
        briefing.fetch_reader = lambda since: [dict(nl, id=21), dict(sem_nl, id=24)]
        sys.argv = ["briefing.py", "--since-hours", "6"]
        briefing.main()
        assert not (briefing.OUTPUT / "briefing-2026-10-26-midday").exists(), "the same newsletters again: nothing to publish"
    finally:
        for k, v in real.items(): setattr(briefing, k, v)

# ------------------------------------------------------------------ admin mail never reaches the edition
mail = lambda title, author="", source="Substack newsletters": dict(id=hash(title) % 10 ** 6, title=title, author=author, _source=source, _section="Business", published="2026-10-26T08:00:00.000000Z",
                                                                  content="<p>" + "Some words here for the body. " * 40 + "</p>", url="https://example.org/" + str(hash(title) % 1000))
admin = [mail("Please verify your email address", source="Financial Times"), dict(mail("Welcome to Axios Pro Rata", "Dan Primack", "Axios"), content="<p>Thanks for subscribing to Axios Pro Rata. " + "More words here. " * 30 + "</p>"), mail("Integration complete!", "Brendan Keeler"),
         mail("Confirm your email change (step 1 of 2)", "Substack"), mail("Events: Subscription Confirmed", "Rock Health", "Rock Health"), mail("Announcing the Third a16z New Media Fellowship", "Gaby Goldberg", "a16z"),
         mail("Thursday: Merck on cancer vaccines", "Endpoints Events", "Endpoints News"), mail("Is your drug working?", "Endpoints Webinars", "Endpoints News"),
         mail("Nature Briefing: Translational Research - Opt-in request", source="Nature Briefing"), mail("Your FT.com email address has been changed", "Financial Times", "Financial Times"),
         mail("Moderna CEO on what's next after success in cancer vaccine", "STAT+ Alert | Adam Feuerstein", "STAT")]
arts_, promos_, _, _ = briefing.build_articles(admin + [mail("A real essay about markets and money", "Jane Doe", "Some Writer")])
assert [a["title"] for a in arts_] == ["A real essay about markets and money"], [a["title"] for a in arts_]
news = [mail(t, "Jane Doe", "Financial Times") for t in ("Senate confirms Fed nominee", "Verification of the trial data is delayed", "Welcome to the new era of AI chips", "Fellowship programme funds 40 scientists")]
assert not any(briefing.R.admin(x) for x in news), "headlines that only contain an admin word are journalism"
six = [dict(full("AI", f"AI piece {n}", f"https://example.org/ai{n}", score=10 - n), full=True) for n in range(7)]
six[6]["must"] = True
assert [a["title"] for a in briefing.chosen(six)] == ["AI piece 6", "AI piece 0", "AI piece 1", "AI piece 2"], "4 articles in full, a Must read first"
stat_news = [mail("Serious adverse events halt a gene therapy trial", "STAT | Health Care Inc.", "STAT"), mail("Novartis raises its offer for a biotech", "Ed Silverman", "STAT")]
assert not any(briefing.R.stat_noise(x) for x in stat_news) and briefing.R.stat_noise(mail("Join us: STAT Summit livestream", "STAT Events", "STAT")), "STAT journalism stays; its promotions go"
short_feed = dict(mail("Anthropic S-1 as it happened: inside the plan", "client.support@ft.com", "FT Alphaville"), content="<p>Short feed title only.</p>")
arts_, _, _, shorts_ = briefing.build_articles([short_feed])
assert arts_ == [] and shorts_[0]["title"].startswith("Anthropic S-1") and shorts_[0]["author"] == "", "a feed item under 60 words is an Also today line, not a piece"
assert briefing.by_author(dict(author="client.support@ft.com", source="FT Alphaville")) == "", "an address is not a journalist"

# ------------------------------------------------------------------ the section layout: anchor, one newsletter per publication, articles, Also today
nlp = lambda title, source, author="", score=5: dict(title=title, source=source, author=author, author_raw=author, section="Markets & Macro", daily=True, words=500, mins=2, html="<p>x</p>", url="https://example.org/" + title, score=score, date="2026-10-26")
morning = dict(nlp("Netanyahu gains the edge", "Bloomberg", "Bloomberg", score=1), html="<p>Netanyahu Overtakes Eisenkot</p><p>Good morning. Netanyahu leads in Israel.</p>")
econ_daily = nlp("Economics Daily: The fall in France", "Bloomberg", score=9)
markets_am = nlp("Markets A.M.: Cartoon apes", "The Wall Street Journal", "Spencer Jakab", score=2)
ftb_ = nlp("Markets afternoon briefing: French bonds", "Financial Times", "FT Briefing", score=3)
unhedged = nlp("Unhedged: The bond market's quiet week", "Financial Times", "Robert Armstrong", score=4)
arts_m = [dict(full("Markets & Macro", f"Article {n}", f"https://example.org/a{n}", score=n)) for n in range(7)]
logs = []
laid, lists_m = briefing.compose([econ_daily, markets_am, morning, ftb_, unhedged, *arts_m], [], log=logs.append)
assert [a["title"] for a in laid][:3] == ["Netanyahu gains the edge", "Markets A.M.: Cartoon apes", "Unhedged: The bond market's quiet week"], [a["title"] for a in laid]
assert [(x["title"], x["source"]) for x in lists_m["Markets & Macro"]][:2] == [("The fall in France", "Bloomberg · Economics Daily"), ("French bonds", "Financial Times · Markets afternoon briefing")], "only the stack prints; any other newsletter is one Also today line, with its newsletter named (Andrea, 28 and 30 Oct 2026)"
assert [a["title"] for a in laid if a.get("role") == "article"] == ["Article 6", "Article 5", "Article 4", "Article 3"] and len(lists_m["Markets & Macro"]) == 5, "four articles by score without an editor, the rest in Also today"
assert logs == ["Anchor: World: The Economist, The World in Brief did not arrive and no other daily newsletter did", "Anchor: Deals & Investing: Axios Pro Rata did not arrive and no other daily newsletter did",
                "Anchor: Biotech & Health: STAT Morning Rounds did not arrive and no other daily newsletter did", "Anchor: AI: Bloomberg AI Today did not arrive and no other daily newsletter did"], logs
# The stack per section (Andrea, 28 Oct 2026): World prints World in Brief, US in Brief and Semafor Flagship; Biotech prints STAT Morning Rounds, The Readout and MedTech Dive;
# AI prints Bloomberg AI Today and Semafor Technology. FirstFT, What's News, Endpoints and the rest are Also today lines.
nl = lambda section, title, source, author="", score=5, html="<p>x</p>": dict(nlp(title, source, author, score), section=section, html=html)
world = [nl("World", "FirstFT: Netanyahu leads", "Financial Times", "FirstFT Americas", 9), nl("World", "The US in Brief: Crude politics", "The Economist · US in Brief", "The Economist", 2),
         nl("World", "🟡 A forever stalemate", "Semafor", "Semafor Flagship", 3), nl("World", "The World in Brief: Netanyahu", "The Economist · World in Brief", "The Economist", 1),
         nl("World", "Apple Knows Some iPhone Duos", "The Wall Street Journal", "WSJ What's News", 8)]
bio = [nl("Biotech & Health", "Makary's exit exhale", "Endpoints News", "Endpoints | Main Edition", 9), nl("Biotech & Health", "Lilly's triple-G drug", "STAT", "STAT | The Readout", 2),
       nl("Biotech & Health", "Inside the bold new biotech", "STAT", "STAT | Morning Rounds", 1), nl("Biotech & Health", "Medtronic's renal denervation", "MedTech Dive", "MedTech Dive", 3)]
ai = [nl("AI", "AI Today: An IPO is just the start", "Bloomberg", "Bloomberg", 2), nl("AI", "🟡 Pit stop", "Semafor", "Semafor Technology", 3)]
laid, lists_s = briefing.compose([*world, *bio, *ai], [], log=lambda m: None)
printed = lambda sec: [a["title"] for a in laid if a["section"] == sec and a.get("role") in ("anchor", "daily")]
assert printed("World") == ["The World in Brief: Netanyahu", "The US in Brief: Crude politics", "🟡 A forever stalemate"], printed("World")
assert sorted(x["title"] for x in lists_s["World"]) == ["Apple Knows Some iPhone Duos", "Netanyahu leads"]
assert printed("Biotech & Health") == ["Inside the bold new biotech", "Lilly's triple-G drug", "Medtronic's renal denervation"] and [x["title"] for x in lists_s["Biotech & Health"]] == ["Makary's exit exhale"], printed("Biotech & Health")
assert printed("AI") == ["AI Today: An IPO is just the start", "🟡 Pit stop"], printed("AI")

# ------------------------------------------------------------------ the same story once across the edition
blocks = lambda *heads: "".join(f"<h2>{h}</h2><p>{h} and more words about it.</p>" for h in heads)
w1 = dict(nlp("Semafor Flagship", "Semafor"), section="World", html=blocks("Lula wins Brazil", "Gaza truce holds"), role="anchor")
m1 = dict(nlp("Markets A.M.", "The Wall Street Journal"), html=blocks("Lula wins, markets fall", "Stocks rise"), role="anchor")
art_dup = dict(full("Markets & Macro", "Brazil's markets after Lula", "https://example.org/b"), role="article")
lines_ = {"Markets & Macro": [dict(title="Gaza truce holds for a week", url="https://example.org/g", source="FT", author="", score=0)]}
def same(prompt):
    rows = [json.loads(r) for r in prompt.split("BLOCKS\n", 1)[1].splitlines()]
    pick = lambda word: [r["id"] for r in rows if word in r["text"]]
    return {"same": [pick("Lula"), pick("Gaza")], "depth": []}
kept, lists2, collapsed = briefing.dedupe_edition([w1, m1, art_dup], lines_, ask=same)
assert "Lula wins Brazil" in w1["html"] and "Lula wins, markets fall" in m1["html"] and "Stocks rise" in m1["html"], "a printed newsletter is never cut: it stays whole (Andrea, 28 Oct 2026)"
assert art_dup not in kept and lists2 == {} and len(collapsed) == 2, "a later full article without new depth and a repeated Also today line go"
# ------------------------------------------------------------------ Long reads: 4 essays, Stratechery, Money Stuff and The Diff first whenever they arrived
essay_ = lambda title, source, author="", score=5, words=2000, **kw: dict(full("Long reads", title, "https://example.org/" + title.replace(" ", "-"), source=source, author=author, author_raw=author, score=score, words=words, fulltext=False), **kw)
minor = [essay_("Beware of Subgroups", "Sensible Medicine", score=9, full=True), essay_("Import AI 478", "Import AI", "Jack Clark", score=8, full=True),
         essay_("What Does It Mean to Know Medicinal Chemistry", "In the Pipeline", score=7, full=True), essay_("PTW/PI All-Stars Book Club – Chapter Twenty-Five", "Roger Martin", score=9, full=True),
         essay_("Let Chaos Reign", "a16z", score=6, full=True)]
majors = [essay_("Money Stuff: Anthropic Raises Concerns", "Bloomberg", "Matt Levine", score=2), essay_("Robots Are Coming for Jobs That Don't Exist Yet", "The Diff (Byrne Hobart)", "Byrne Hobart", score=1),
          essay_("The End of the Internet", "Stratechery", "Ben Thompson", score=3)]
headline_only = dict(title="The infinite work machine", url="https://example.org/odd-lots", source="Bloomberg", author="Odd Lots", section="Long reads")
laid, lists_l = briefing.compose([*minor, *majors], [headline_only], log=lambda m: None)
full_l = [a["title"] for a in laid if a["section"] == "Long reads"]
assert full_l == ["The End of the Internet", "Money Stuff: Anthropic Raises Concerns", "Robots Are Coming for Jobs That Don't Exist Yet", "Beware of Subgroups"], full_l
also_l = [x["title"] for x in lists_l["Long reads"]]
assert "PTW/PI All-Stars Book Club – Chapter Twenty-Five" in also_l and "The infinite work machine" in also_l and "Import AI 478" in also_l and not set(also_l) & set(full_l), "the rest, social posts and headline-only items are Also today lines"
laid, lists_l = briefing.compose(list(minor), [], log=lambda m: None)
assert [a["title"] for a in laid if a["section"] == "Long reads"] == ["Beware of Subgroups", "Import AI 478", "What Does It Mean to Know Medicinal Chemistry", "Let Chaos Reign"], "without the three, the editor's picks take the 4 slots; a book club post never does"
quoting = essay_("Why Money Stuff and The Diff matter to markets", "Some Writer", "Jane Roe", score=1)
assert R.long_read_rank(quoting) is None and R.long_read_rank(majors[0]) == 1 and R.long_read_rank(majors[1]) == 2 and R.long_read_rank(majors[2]) == 0, "a slot by source and author, never by words in a title"
many = [essay_(f"Stratechery post {n}", "Stratechery", "Ben Thompson", score=n) for n in range(5)]
laid, _ = briefing.compose(many + minor[:1], [], log=lambda m: None)
assert len([a for a in laid if a["section"] == "Long reads"]) == 4, "never more than 4 essays, however many of the three arrived"
assert briefing.R.chatter(essay_("A short note", "Some Writer", words=250)) and not briefing.R.chatter(essay_("A real essay", "Some Writer", words=1200)), "a piece under 300 words is not an essay"
sent = []
real = briefing.ask_model, briefing.shutil.which, briefing.PROFILE
with tempfile.TemporaryDirectory() as tmp:
    try:
        briefing.PROFILE = pathlib.Path(tmp) / "interests.md"; briefing.PROFILE.write_text("Finance first.")
        briefing.ask_model = lambda prompt: sent.append(prompt); briefing.shutil.which = lambda name: "/usr/bin/" + name
        briefing.ask_editor([*minor[:3]])
    finally: briefing.ask_model, briefing.shutil.which, briefing.PROFILE = real
assert len(sent) == 1 and all(R.READER_SOURCES in p for p in (sent[0], H.RANK_PROMPT)), "every ranking and selection prompt names the reader's top sources"
assert briefing.EDITOR_MODEL == "opus" and briefing.EDITOR_TIMEOUT >= 600, "one shared model setting, Opus, with time to answer"

# ------------------------------------------------------------------ an Also today line never shows markup a title carries
marked = [dict(title='<a href="https://www.thediff.co/archive/x/">Longreads + Open Thread</a>', url="https://www.thediff.co/archive/x/", source="The Diff", author=""),
          dict(title='&lt;a href="https://www.thediff.co/archive/y/"&gt;Robots &amp; jobs&lt;/a&gt;', url="https://www.thediff.co/archive/y/?a=1&b=2", source="The Diff", author="Byrne <b>Hobart</b>")]
out = H.lines_html(marked, lambda p: "a1", "Also today")
shown = BeautifulSoup(out, "lxml").get_text(" ")
assert "<a" not in shown and "href" not in shown and "Longreads + Open Thread" in shown and "Robots & jobs" in shown and "Byrne Hobart" in shown, shown
assert "href='https://www.thediff.co/archive/y/?a=1&amp;b=2'" in out and out.count("<a ") == 2, "the link itself stays a link, its address escaped once"

# ------------------------------------------------------------------ direct links: every link in a printed piece points at its article (Andrea, 29 Oct 2026: links on the Kindle hung)
import base64 as _b64m  # noqa: E402
axios_link = "https://link.axios.com/click/41234.5678/" + _b64m.urlsafe_b64encode(b"https://www.axios.com/2026/10/28/pe-politics?utm_source=newsletter").decode().rstrip("=") + "/abc"
bb = "https://links.message.bloomberg.com/a/sc/zzbCLytlreF4OS"
eco = "https://click.e.economist.com/?qs=abc123"
stat = "https://marketing.statnews.com/e/er?s=1&lid=2"
unsub = "https://links.message.bloomberg.com/a/sc/UNSUB"
requests = []
def fake_curl(url, *args):
    requests.append(url)
    return {bb: "https://www.bloomberg.com/news/articles/2026-10-28/fed-holds?srnd=x&utm_medium=email", eco: "https://www.economist.com/finance/2026/10/28/a-story"}.get(url, "")
piece = (f"<p><a href='{axios_link}'>PE politics</a> and <a href='{bb}'>the Fed holds rates</a>, <a href='{eco}'>a story about markets</a>, <a href='{stat}'>STAT</a>.</p>"
         f"<p><a href='{unsub}'>Unsubscribe</a> | <a href='mailto:x@y.z'>write</a> | <a href='#top'>top</a> | <a href='https://ad.doubleclick.net/x'>Ad</a></p>")
cache = {}
out = H.direct_links(piece, fake_curl, lambda s: None, cache)
assert "https://www.axios.com/2026/10/28/pe-politics" in out and "utm_source" not in out, "a tracker that carries its target is decoded, with no request"
assert "https://www.bloomberg.com/news/articles/2026-10-28/fed-holds" in out and "links.message.bloomberg.com/a/sc/zzb" not in out, "Bloomberg's tracker is followed one hop to the article"
assert "https://www.economist.com/finance/2026/10/28/a-story" in out, "the Economist's tracker is followed; the article address is never requested"
assert stat in out.replace("&amp;", "&"), "a tracker that cannot be followed safely stays as it is"
assert "Unsubscribe" in out and unsub not in out and "doubleclick" not in out and ">Ad<" not in out.replace("</a>", ""), "an unsubscribe or advertising link loses its link and is never requested"
assert "mailto:x@y.z" in out and ("href=\"#top\"" in out or "href='#top'" in out), "mail and in-page links are left alone"
assert requests == [bb, eco] and not any("bloomberg.com/news" in r or "economist.com/finance" in r for r in requests), requests
H.direct_links(piece, fake_curl, lambda s: None, cache); assert requests == [bb, eco], "each tracker is asked once per edition"
requests.clear(); many_links = "".join(f"<a href='https://links.message.bloomberg.com/a/sc/n{n}'>a story number {n}</a>" for n in range(H.FOLLOW_MAX + 5))
H.direct_links(many_links, fake_curl, lambda s: None, {}); assert len(requests) == H.FOLLOW_MAX, "at most FOLLOW_MAX trackers are asked per edition"

requests.clear(); risky = "".join(f"<a href='https://links.message.bloomberg.com/a/sc/r{n}'>{t}</a>" for n, t in enumerate(["Click here", "Update", "", "<img src='x.png'>", "Stop receiving these emails"]))
out = H.direct_links(risky, fake_curl, lambda s: None, {})
assert requests == [] and "Stop receiving" in out and "/a/sc/r4" not in out, "a tracker behind short, image or admin text is never asked; admin text loses its link"
assert not H.FOLLOWABLE.match("elink3f6.outofpocket.health"), "Out-of-Pocket's tracker gives no plain redirect and is not followed"

print("briefing headline checks passed")
