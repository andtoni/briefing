#!/usr/bin/env python3
"""Source checks for the Briefing job; the cleaning test runs wherever its two libraries are installed."""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOB = ROOT / "briefing"

for name in ("briefing.py", "clean.py", "rules.py"):
    ast.parse((JOB / name).read_text(), filename=name)

source = (JOB / "briefing.py").read_text()
for forbidden in ("-X','POST", "-X','DELETE", "-X','PATCH", "unread_entries"):
    assert forbidden not in source, f"briefing.py must stay read-only against its sources: {forbidden}"
assert "%%BOOK%%" in (JOB / "template.html").read_text()
assert "while target.exists()" in source, "a published path must never be overwritten"

try:
    import bs4  # noqa: F401
    import lxml  # noqa: F401
except ImportError:
    print("briefing source checks passed (cleaning test skipped: beautifulsoup4/lxml not installed)")
    sys.exit(0)

sys.path.insert(0, str(JOB))
import os  # noqa: E402
os.environ.setdefault("BRIEFING_TZ", "Africa/Johannesburg")  # the checks were written for a Cape Town reader: Morning before 11:00 local time
import briefing  # noqa: E402

body = "<p>" + " ".join(["A real sentence about a policy change."] * 60) + "</p>"
entry = dict(
    id=1, feed_id=1, title="Example", author="A. Writer", url="https://example.org/a",
    published="2026-01-01T06:00:00.000000Z", _source="Example Letter", _section="World",
    content="<table><tr><td><img src='https://example.org/pixel.gif' width='1' height='1'>" + body
    + "<p>This email was sent to you because you subscribed.</p></td></tr></table>",
)
article = briefing.prep(entry)
assert article["words"] > 300, article["words"]
assert "This email was sent" not in article["html"]
assert "pixel.gif" not in article["html"]
articles, promos, _, _ = briefing.build_articles([entry, dict(entry, id=2, title="Verify your email address")])
assert len(articles) == 1 and len(promos) == 1
plain = briefing.prep(dict(entry, id=3, content=" ".join(["Plain text with no markup at all."] * 10)))
assert plain["words"] == 70 and plain["html"].startswith("<p"), plain
import datetime, json, re, tempfile  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
pieces = [dict(title=f"T{n}", source=f"S{n}", section="World", words=300 + n, html="<p>x</p>", url=f"https://example.org/{n}") for n in range(4)]
edited = briefing.apply_edit(pieces, {"score": {"0": 3, "1": 9, "2": "bad", "9": 5}, "same": [[0, 1], [3], [7, 8]],
                                      "front": [{"id": 1, "line": "No longer asked for."}]})
assert [p["title"] for p in edited] == ["T1", "T2", "T3"], "the lower-scored duplicate is folded into the kept piece"
assert "Also covered by" in edited[0]["html"] and "front" not in edited[0], "the editor's reply no longer carries front-page lines"
fresh = [dict(title="A", source="S", section="World", words=300, html="<p>x</p>", url="")]
assert briefing.apply_edit(list(fresh), None) == fresh and briefing.apply_edit(list(fresh), {"same": "x", "front": 3, "score": []}) == fresh, "a malformed reply changes nothing"
assert "grayscale" not in (JOB / "template.html").read_text(), "pictures keep their own colours"
assert "'--tools',''" in source, "the editor run gets no tools: the pieces are untrusted text"
mf_source = (JOB / "miniflux.py").read_text()
assert "BACKLOG_DAYS" in mf_source and "PER_FEED" in mf_source and "back catalogue" in mf_source, "a newly added feed must not flood an edition with old posts"
FIXTURE = (ROOT / "tests/fixtures/github_trending.html").read_text()
repos = briefing.parse_trending(FIXTURE)
assert [r["name"] for r in repos][:5] == ["morluto/rea", "bilawalsidhu/gods-eye-view", "debpalash/VoiceStudio", "mksglu/context-mode", "cathrynlavery/diagram-design"] and len(repos) == 9, "every row on the page, no top-N"
assert repos[0] == dict(name="morluto/rea", url="https://github.com/morluto/rea", lang="TypeScript", gain="54,679", total="216,660",
                        desc="Reverse engineer anything with agents, from app behavior down to native binaries."), repos[0]
assert briefing.parse_trending("<html>blocked</html>") == [] and briefing.build_trending([], "2026-10-14") == []
assert briefing.clean_desc(":rocket: 🚀 A fast  tool , see https://x.io |") == "A fast tool, see" and briefing.clean_desc("w " * 200).endswith("…")
assert briefing.vague("") and briefing.vague("My dotfiles") and not briefing.vague(repos[0]["desc"])
# A missing or vague description is summarised by one tool-less model run with a clean environment; a failed run keeps the original text.
calls = []
def fake_run(cmd, **kw):
    calls.append((cmd, kw["env"]))
    return type("R", (), {"stdout": 'Sure: {"a/b": "Turns spreadsheets into charts for analysts."}'})()
real_run, real_which, real_curl, real_firecrawl = briefing.subprocess.run, briefing.shutil.which, briefing.curl, briefing.firecrawl
briefing.subprocess.run, briefing.shutil.which, briefing.curl = fake_run, lambda _x: "/bin/claude", lambda *_a, **_k: "# a/b\nreadme"
os_env = briefing.os.environ; os_env["BRIEFING_MINIFLUX_TOKEN"] = "x"
thin = briefing.summarise([dict(name="a/b", desc="", lang="", gain="1", total="2"), dict(repos[0])])
assert thin[0]["desc"] == "Turns spreadsheets into charts for analysts." and thin[0]["ai"] and "ai" not in thin[1]
assert len(calls) == 1 and calls[0][0][-2:] == ["--tools", ""], calls
assert "BRIEFING_MINIFLUX_TOKEN" not in calls[0][1], "the summary run gets none of the job's credentials"
briefing.subprocess.run = lambda *_a, **_k: type("R", (), {"stdout": "not json"})()
assert briefing.summarise([dict(name="a/b", desc="tool", lang="", gain="1", total="")])[0]["desc"] == "tool"
briefing.subprocess.run, briefing.shutil.which, briefing.curl = real_run, real_which, real_curl
del os_env["BRIEFING_MINIFLUX_TOKEN"]
trend = briefing.build_trending(repos, "2026-10-14")
assert len(trend) == 1 and trend[0]["section"] == "GitHub Trending" and trend[0]["html"].count("class='job'") == 9
assert "href='https://github.com/morluto/rea'" in trend[0]["html"] and "★ 54,679 today" in trend[0]["html"] and "216,660" not in trend[0]["html"], "one row: rank, linked name, gain, one-line brief; no extra detail"
assert re.findall(r"class='sc (\w+)'>(\d)<", trend[0]["html"])[:5] == [("hi", "1"), ("hi", "2"), ("hi", "3"), ("mid", "4"), ("mid", "5")], "coloured by rank"
with tempfile.TemporaryDirectory() as tmp:
    briefing.TRENDING_SEEN = pathlib.Path(tmp) / "trending_seen"
    briefing.FIRECRAWL_KEY = ""
    def broken(*_a, **_k): raise OSError("no network")
    briefing.curl = broken
    assert briefing.fetch_trending("2026-10-14") == [], "a failed fetch only leaves the section out"
    model = briefing.EDITOR_MODEL; briefing.EDITOR_MODEL = ""
    briefing.curl = lambda url, *_a, **_k: FIXTURE
    assert len(briefing.fetch_trending("2026-10-14")) == 9
    briefing.TRENDING_SEEN.write_text("2026-10-14\n")
    assert briefing.fetch_trending("2026-10-14") == [], "a second edition that day does not repeat it"
    briefing.curl, briefing.firecrawl, briefing.EDITOR_MODEL = real_curl, real_firecrawl, model
assert "trending=build_trending(fetch_trending(day),day) if edition=='Morning' else []" in source, "GitHub Trending is morning-only"
assert not any(hasattr(briefing, k) for k in ("CLAUDE_TRENDING", "CLAUDE_SEEN", "fetch_claude_trending", "parse_claude_trending", "build_claude_trending")) and "findarepo" not in source, "Claude Code Trending is gone (Andrea, 27 Oct 2026)"
now = datetime.datetime(2026, 10, 14, 7, 15, tzinfo=briefing.TZ)
world = dict(title="A world story", source="Paper", section="World", author="", date="2026-10-14", words=300, mins=1, html="<p>" + "word " * 100 + "</p>")
_, _, book = briefing.render([dict(world), dict(trend[0])], [], now, "Morning")
order = [book.index(m) for m in ('class="masth">The Briefing<', 'id="toc"', 'data-title="World"', 'data-title="GitHub Trending"')]
assert order == sorted(order) and 'id="cover"' not in book, "no cover: the heading, the Contents, the news sections, then the repository list at the very end"
for title in ("GitHub Trending",):
    sec = book[book.index(f'data-title="{title}"'):]
    sec = sec[:sec.index("</article>")]
    assert 'class="sitem"' not in sec and "In this issue" not in sec, f"the {title} section is one list, without its own index"
toc = book[book.index('id="toc"'):book.index("</section>", book.index('id="toc"'))]
assert all(f'data-go="s{k}"' in toc for k in range(2)) and toc.count('class="titem"') == 2, "Contents lists every section and every piece under it"
assert book.index('id="toc"') < book.index('id="s0"'), "the Contents comes before the first section"
authored = [dict(world, title="Essay", source="Money Stuff", author="Matt Levine", mins=13), dict(world, title="Same", source="The Economist", author="The Economist"),
            dict(world, title="Dated", source="Axios Pro Rata", author=" Dan Primack  · Oct 21"), dict(world, title="Bare"), dict(world, title="Long", author="x" * 60)]
_, _, authored_book = briefing.render(authored, [], now, "Morning")
contents = authored_book[authored_book.index('id="toc"'):authored_book.index("</section>", authored_book.index('id="toc"'))]
lines = {m[0]: m[1] for m in re.findall(r'<span class="tt">([^<]*)</span><span class="tm">(.*?)</span></a>', contents)}
assert lines["Essay"] == " — <b>Money Stuff</b> · Matt Levine · 13 min", lines["Essay"]
assert lines["Same"] == " — <b>The Economist</b> · 1 min" and lines["Bare"] == " — <b>Paper</b> · 1 min" and lines["Long"] == " — <b>Paper</b> · 1 min", "no author when it repeats the publication, is missing, or is not a name"
assert lines["Dated"] == " — <b>Axios Pro Rata</b> · Dan Primack · 1 min", "a byline with a date keeps the name only"
assert briefing.byline(dict(source="The Wall Street Journal", author="Spencer Jakab, WSJ")) == "<b>The Wall Street Journal</b> · Spencer Jakab" and briefing.byline(dict(source="Bloomberg", author="Bloomberg Odd Lots")) == "<b>Bloomberg</b> · Odd Lots" and briefing.byline(dict(source="Financial Times", author="FT Briefing")) == "<b>Financial Times</b>", "the publication in bold, then the journalist; a series name is not a journalist"
ends = re.findall(r'<div class="endnav">(.*?)</div>', book)
assert ends[0].startswith('<a href="#toc" data-go="toc">‹ Previous</a>') and all(f'href="#a{i - 1}" data-go="a{i - 1}">‹ Previous</a>' in e for i, e in enumerate(ends) if i), "each story ends with ‹ Previous (the Contents for the first story)"
assert all('data-go="toc">Contents</a>' in e for e in ends) and all(f'Next: ' in e for e in ends[:-1]) and "Next:" not in ends[-1], "Contents and Next stay"
# EPUB: reflowable, made by pandoc; chapters, nav and internal links survive, and every list item is a real block for Kindle. The stylesheet fights no device setting.
css = (JOB / "epub.css").read_text()
assert not re.search(r"column|(?<![-\w])(width|height)\s*:\s*(?!auto|\d+%)|\d(px|pt|in|cm|mm)\b|@page|rendition:layout", css.split("*/", 1)[1]), "relative units only, no columns or fixed sizes"
assert not re.search(r"flex|grid|float|inline-block|position\s*:|background", css.split("*/", 1)[1]), "Kindle-safe CSS: no flex, grid, floats, inline-block, positioning or fills"
if briefing.shutil.which("pandoc"):
    import zipfile
    _, _, book = briefing.render([dict(world), dict(trend[0])], [], now, "Morning")
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "b.epub"
        assert briefing.write_epub(book, now, "Morning", out)
        with zipfile.ZipFile(out) as z:
            text = "".join(z.read(n).decode() for n in z.namelist() if n.endswith(".xhtml")); opf = z.read("EPUB/content.opf").decode(); nav = z.read("EPUB/nav.xhtml").decode()
            ncx = z.read("EPUB/toc.ncx").decode(); names = z.namelist(); first = z.read("EPUB/text/ch001.xhtml").decode(); sheet = z.read("EPUB/styles/stylesheet1.css").decode()
        assert "pre-paginated" not in opf and "nav" in opf, "reflowable, with a nav"
        assert "class=\"sc" not in text and "style=" not in text and 'class="item"' in text, "no colour chips; items are blocks"
        assert re.search(r'<p>\s*<strong>World</strong>\s*</p>\s*<div class="item">\s*<p><strong>A world story</strong> <a href="ch\d+\.xhtml#a\d">Read ›</a></p>\s*<div class="src">\s*<strong>Paper</strong>\s*</div>', text), "the group, then the line in plain bold with a small Read › link and its publication under it"
        assert not re.search(r"<a [^>]*>\s*<(div|span)", text), "no link wraps a layout block"
        assert not any("title_page" in n for n in names), "no separate title page"
        assert "cover-image" not in opf and not any("cover" in n for n in names) and "cover_xhtml" not in opf, "no cover, not even a cover image"
        assert re.search(r'<div class="by">\s*<strong>Paper</strong> · ', text), "each story names its source under the title"
        assert not re.search(r'<div class="secm">[^<]*</div>\s*<div class="tnav">', text) and re.search(r'</h3>\s*<div class="tnav">', text) and 'class="tnav end"' in text, "no duplicated section nav; every story keeps its own"
        assert first.count(">The Briefing</h1>") == 1 and 'id="contents"' in first and all(t in first for t in ("A world story", "9 repositories trending today")), "one opening page: title, then Contents listing every story"
        assert re.search(r'<div[^>]*class="ts">\s*<a href="ch\d+\.xhtml#a\d">A world story</a> — <strong>Paper</strong> · 1 min\s*</div>', first), "each story on one line: linked title, then its publication"
        world_id = re.search(r'<a href="ch\d+\.xhtml#(a\d)">A world story</a>', first)[1]
        assert f'id="c-{world_id}"' in first and re.search(rf'href="ch001\.xhtml#contents">‹ Previous</a> · <a href="ch001\.xhtml#c-{world_id}">Contents</a> · <a href="ch\d+\.xhtml#a\d">Next ›', text) and 'id="toc"' not in first, "under each title: ‹ Previous (the Contents for the first story), Contents (its own entry) and Next"
        assert re.search(rf'<div class="tnav end">\s*<a href="ch001\.xhtml#contents">‹ Previous</a> · <a href="ch001\.xhtml#c-{world_id}">Contents</a> · <a href="ch\d+\.xhtml#a\d">Next ›', text), "at each story's end: ‹ Previous · Contents · Next ›"
        ids = re.findall(r'<h3 class="story[^"]*" id="(a\d)"', text)
        for k, sid in enumerate(ids[1:], 1):
            assert re.search(rf'<h3 class="story[^"]*" id="{sid}">.*?<div class="tnav">\s*<a href="ch\d+\.xhtml#{ids[k - 1]}">‹ Previous</a>', text, re.S), "a later story's Previous is the story before"
        assert 'href="text/ch001.xhtml#contents"' in opf and 'epub:type="landmarks"' in nav and 'epub:type="toc" href="text/ch001.xhtml#contents"' in nav, "Go To > Contents lands on the Contents page"
        assert len(re.findall("<navPoint", ncx)) == len(re.findall(r"<li[ >]", nav)) - 2, "the NCX lists every nav entry"
        assert len(re.findall(r'<h3 class="story', text)) == 2 and "page-break-before" not in sheet and len([n for n in names if re.search(r"text/ch\d+\.xhtml$", n)]) == 1, "one continuous chapter: no section or story starts a page"
        tocnav = BeautifulSoup(nav, "xml").find("nav", attrs={"id": "toc"}).find("ol")
        top = [li.find("a").get_text() for li in tocnav.find_all("li", recursive=False)]
        world_li = next(li for li in tocnav.find_all("li", recursive=False) if li.find("a").get_text() == "World")
        assert "World" in top and "GitHub Trending" in top and [a.get_text() for a in world_li.find("ol").find_all("a")] == ["A world story"], ("a two-level nav: the sections, each with its stories", top)
        ncxmap = BeautifulSoup(ncx, "xml").navMap
        assert [p.navLabel.get_text(strip=True) for p in ncxmap.find_all("navPoint", recursive=False)][1:] == top[1:], "the NCX is nested the same way"
        assert re.search(r'href="ch\d+\.xhtml#a\d"', text), "internal links point at their chapter"
        assert all(t in nav for t in (">Contents<", ">The day in two minutes<", ">GitHub Trending<", ">World<", ">A world story<")), "the nav lists every section and piece"
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        big, dest = pathlib.Path(tmp) / "big.png", pathlib.Path(tmp) / "out.jpg"
        Image.new("RGB", (3000, 2000), (200, 30, 30)).save(big)
        assert briefing.kindle_image(big.as_uri(), dest), "a local picture converts"
        with Image.open(dest) as im: assert im.mode == "L" and max(im.size) == briefing.EPUB_IMAGE_EDGE and im.format == "JPEG", "greyscale JPEG, longest side 1264"
        Image.new("RGB", (1200, 240)).save(big)
        assert not briefing.kindle_image(big.as_uri(), dest), "a banner strip is dropped"
        assert briefing.DECORATIVE.search("https://s.wsj.net/newsletter/article-banners/x.png") and not briefing.DECORATIVE.search("https://images.wsj.net/im-60141416?width=600"), "banners and logos by address, news photos kept"
        Image.new("RGB", (1, 1)).save(big)
        assert not briefing.kindle_image(big.as_uri(), dest), "a tracking pixel is dropped"
secs = [(sec, f"Story in {sec}") for sec in ("Biotech & Health", "AI", "Deals & Investing", "Long reads", "World", "Markets & Macro", "Life")]
_, _, book = briefing.render([dict(world, section=sec, title=t) for sec, t in secs], [], now, "Morning")
titles = [briefing.html.unescape(m) for m in re.findall(r'data-title="([^"]+)"><h1 class="sech">', book)]
assert titles == ["World", "Markets & Macro", "Deals & Investing", "Biotech & Health", "AI", "Long reads", "Life"], titles
assert [book.index(f"Story in {x}") for x in ("World", "Markets", "Biotech")] == sorted(book.index(f"Story in {x}") for x in ("World", "Markets", "Biotech"))
today = book[book.index('id="today"'):book.index('id="toc"')]
assert today.index("Story in World") < today.index("Story in Markets") < today.index("Story in Deals") < today.index("Story in Biotech") < today.index("Story in AI") and "Story in Long reads" not in today and "Story in Life" not in today, "the day in two minutes follows the themes; a long read or a Life piece is not on it unless it is a Must read"
assert briefing.ORDER == ["The week", "World", "Markets & Macro", "Deals & Investing", "Biotech & Health", "AI", "Long reads", "Life", "Saved", "Other", "GitHub Trending"], "The week first, the five themes, the long reads, then the repository list at the very end"
# No section is capped: every piece stays a full piece.
many = [dict(id=n, title=f"Story {n}", source=f"Paper {n}", section="Markets & Macro", author="", date="2026-10-14", words=400, mins=2, url=f"https://example.org/{n}",
             score=n, html="<p>" + f"Opening line of story {n} with enough words to count as a paragraph here. " * 3 + "</p>") for n in range(9)]
assert not hasattr(briefing, "cap_sections") and not hasattr(briefing, "SECTION_CAP"), "no per-section cap"
# Retries: the editor is tried three times with short pauses; the PDF render once more with a longer limit; failures cost only that part.
calls, naps = [], []
def flaky(cmd, **kw):
    calls.append(kw.get("timeout"))
    if len(calls) == 1: raise briefing.subprocess.TimeoutExpired(cmd, 1)
    return type("R", (), {"stdout": "not json" if len(calls) == 2 else '{"score": {}}'})()
real_run, real_which, real_sleep, real_profile = briefing.subprocess.run, briefing.shutil.which, briefing.time.sleep, briefing.PROFILE
with tempfile.TemporaryDirectory() as tmp:
    briefing.PROFILE = pathlib.Path(tmp) / "interests.md"; briefing.PROFILE.write_text("health")
    briefing.subprocess.run, briefing.shutil.which, briefing.time.sleep = flaky, lambda _x: "/bin/x", naps.append
    assert briefing.ask_editor([dict(world)] * 3) == {"score": {}} and len(calls) == 3 and naps == [15, 45], "two retries with a short backoff"
    briefing.subprocess.run = lambda *a, **k: (_ for _ in ()).throw(OSError("down")); naps.clear()
    assert briefing.ask_editor([dict(world)] * 3) is None and naps == [15, 45], "after the last try the edition builds without the editor"
    pdf, limits = pathlib.Path(tmp) / "b.pdf", []
    def render(cmd, **kw):
        limits.append(kw["timeout"])
        if len(limits) == 1: raise briefing.subprocess.TimeoutExpired(cmd, kw["timeout"])
        pdf.write_bytes(b"%PDF")
    briefing.subprocess.run = render
    assert briefing.write_pdf("<p>x</p>", now, "Morning", pdf) and limits == [180, 360], "one PDF retry with a longer limit"
    def boom(*_a, **_k): raise RuntimeError("renderer crashed")
    real_pdf, real_epub = briefing.write_pdf, briefing.write_epub
    briefing.write_pdf, briefing.write_epub = boom, boom
    briefing.documents("<p>x</p>", now, "Morning", pathlib.Path(tmp) / "c.pdf", pathlib.Path(tmp) / "c.epub")      # must not raise
    briefing.write_pdf, briefing.write_epub = real_pdf, real_epub
briefing.subprocess.run, briefing.shutil.which, briefing.time.sleep, briefing.PROFILE = real_run, real_which, real_sleep, real_profile
# Long-read summaries: a very brief "In short" at the top of each long single-author piece, from one batched editor-model run.
import rules  # noqa: E402
essay = lambda **kw: dict(dict(title="An essay", source="Money Stuff", author_raw="Matt Levine", pub="", section="Business", author="Matt Levine", date="2026-10-14", words=3000, mins=13,
                               html="<p>" + "The firm raised 40 million dollars at a high price. " * 300 + "</p>", url="https://example.org/e"), **kw)
assert rules.long_read(essay()) and not rules.long_read(essay(words=1199)) and rules.long_read(essay(words=1200)), "long means at least 1,200 words"
for name, piece in (("Semafor", essay(source="Semafor Flagship")), ("Economist brief", essay(source="The Economist · World in Brief")), ("FirstFT", essay(source="FT newsletters", author_raw="FirstFT Americas")),
                    ("WSJ What's News", essay(source="Emma Tucker, WSJ", author_raw="WSJ What's News")), ("10-Point", essay(source="Emma Tucker, WSJ", title="The 10-Point: A Showdown")),
                    ("markets briefing", essay(source="FT newsletters (Briefing)", title="Markets morning briefing: Oil")), ("Pro Rata", essay(source="Axios Pro Rata")),
                    ("STAT roundup", essay(source="STAT+ Pharmalittle", author_raw="STAT | Pharmalittle", pub="STAT")), ("STAT muted", essay(source="STAT", author_raw="STAT | Daily Recap", pub="STAT")),
                    ("brief feed", essay(brief=True)), ("list section", essay(unit=("post", "posts"))), ("many short stories", essay(html="".join(f"<h2>Story {n}</h2><p>" + "word " * 150 + "</p>" for n in range(8))))):
    assert not rules.long_read(piece), f"{name} is a roundup, not a long read"
assert rules.long_read(essay(title="A weekly habit and a briefing on trust")) and rules.long_read(essay(source="Weekly Dispatch")), "a title or source that merely contains weekly or briefing is still a long read"
assert rules.long_read(essay(source="STAT+ The Readout", author_raw="STAT | The Readout", pub="STAT")) and rules.long_read(essay(source="FT newsletters", author_raw="FT Unhedged", title="Unhedged: Bonds")), "a written STAT newsletter and Unhedged are long reads"
assert rules.long_read(essay(html="".join(f"<h2>Part {n}</h2><p>" + "word " * 700 + "</p>" for n in range(4)))), "an essay with a few long sections is one piece"
assert rules.long_read(essay(html="".join(f"<h2>Part {n}</h2><p>" + "word " * 400 + "</p>" for n in range(7)))), "many headings over long sections are still one essay"

src = "The firm raised 40 million dollars in 2025 and 1,500 people joined."
ok = "The piece covers one firm's fundraising. It argues that the round was large for its stage and reports 40 million dollars raised."
assert briefing.usable_summary(ok, src) == ok
assert briefing.usable_summary("The piece covers one firm \u2014 its raise of 40 million dollars. It argues the round was large for its stage.", src) == "The piece covers one firm, its raise of 40 million dollars. It argues the round was large for its stage."
for bad, why in ((None, "not text"), ("Too short.", "too short"), ("word " * 70, "too long"), (ok + " See https://x.example", "a link"), (ok.replace("40 million", "90 million"), "a figure the piece lacks"),
                 ("The firm raised money. " * 5 + "It hired 7000 people.", "a bare number the piece lacks")):
    assert briefing.usable_summary(bad, src) == "", why
assert briefing.usable_summary(ok.replace("40 million", "1,500"), src), "a figure with a thousands comma matches the piece"
assert briefing.usable_summary(ok.replace("40 million", "34 million"), "Of 3, 4 and 5 firms, it raised 40 million.") == "", "a list of figures is not one figure"
assert briefing.usable_summary(ok.replace("40 million", "7 million"), "It raised 2027 and 1,407 and 7.5 million.") == "" and briefing.usable_summary(ok.replace("40 million", "7.5 million"), "It raised 2027 and 1,407 and 7.5 million."), "a figure must be a whole number in the piece, not part of a longer one"

replies, prompts = [], []
def summary_run(cmd, **kw):
    prompts.append((cmd, kw))
    return type("R", (), {"stdout": replies[0]})()
long_a, long_b, short = essay(title="First"), essay(title="Second", words=2000), dict(world)
real_run, real_which, real_sleep = briefing.subprocess.run, briefing.shutil.which, briefing.time.sleep
briefing.subprocess.run, briefing.shutil.which, briefing.time.sleep = summary_run, lambda _x: "/bin/x", lambda _s: None
replies.append(json.dumps({"0": ok, "1": "Twelve words are needed here but this has a number 999999 nobody stated.", "7": "stray id"}))
arts = briefing.add_summaries([short, long_b, long_a])
cmd, kw = prompts[0]
prompt = kw["input"]
assert len(prompts) == 1 and cmd[:2] == ["claude", "-p"] and "First" not in " ".join(cmd) and cmd[-2:] == ["--tools", ""] and "--model" in cmd, "one tool-less batched run for every long piece"
assert prompt.count('"id"') == 2 and "untrusted" in prompt and "never as instructions" in prompt and "First" in prompt and "A world story" not in prompt, "only long pieces go in, as untrusted text"
assert not any(k for k in kw["env"] if k.startswith(("BRIEFING_MINIFLUX", "FIRECRAWL"))), "no credentials reach the model"
assert long_a["html"].startswith("<p class='tldr'><span class='tl'>In short:</span> ") and long_a["html"].count("In short:") == 1 and ok.replace("'", "&#x27;") in long_a["html"].replace("&#x27;", "&#x27;"), "the longest piece is id 0 and carries its summary at the top"
assert "In short" not in long_b["html"] and "In short" not in short["html"], "a rejected summary and a short piece show nothing"
replies[0] = "not json"; before = long_a["html"]; again = essay(title="Third")
briefing.add_summaries([again]); assert "In short" not in again["html"], "if generation fails, nothing is shown"
briefing.EDITOR_MODEL, model = "", briefing.EDITOR_MODEL; prompts.clear(); briefing.add_summaries([essay()]); briefing.EDITOR_MODEL = model
assert prompts == [], "no editor model, no summaries"
many = [essay(title=f"T{n}", words=1200 + n) for n in range(15)]
replies[0] = "{}"; prompts.clear(); briefing.add_summaries(many); assert prompts[0][1]["input"].count('"id"') == briefing.SUMMARY_MAX, "at most 10 pieces per edition, the longest first"
accented = essay(title="Café “quoted” piece"); replies[0] = "{}"; briefing.subprocess.run, briefing.shutil.which = summary_run, lambda _x: "/bin/x"; prompts.clear()
briefing.add_summaries([accented]); assert "Café “quoted”" in prompts[0][1]["input"] and "\\u" not in prompts[0][1]["input"], "non-ASCII text is sent as it is, not as six-byte escapes"
briefing.subprocess.run, briefing.shutil.which, briefing.time.sleep = real_run, real_which, real_sleep
piece = essay(); piece["html"] = f"<p class='tldr'><span class='tl'>In short:</span> {ok}</p>" + piece["html"]
_, _, book = briefing.render([piece, dict(world)], [], now, "Morning")
story = book[book.index("In short:"):]
assert book.count("In short:") == 1 and story.index("The firm raised") < len(ok) + 150, "the summary opens the story in the HTML and PDF"
assert book.count(ok) == 1, "the summary is not repeated as the section index's teaser"
for page in ("template.html", "print.html"):
    assert "p.tldr" in (JOB / page).read_text() and "font-style:italic" in (JOB / page).read_text().split("p.tldr", 1)[1][:80], f"{page} styles the summary quietly: italic, small lead, no box or fill"
if briefing.shutil.which("pandoc"):
    with tempfile.TemporaryDirectory() as tmp:
        epub = pathlib.Path(tmp) / "s.epub"; briefing.write_epub(book, now, "Morning", epub)
        with zipfile.ZipFile(epub) as z: text = "".join(z.read(n).decode() for n in z.namelist() if n.endswith(".xhtml"))
        assert "In short: <em>" in text and ok in text.replace("&#39;", "'"), "the summary is in the EPUB, in italics after its plain lead"
# Must read, and no repeats across editions: both come from the editor's one run.
def plain_piece(n, **kw): return dict(dict(title=f"Story {n}", source=f"Paper {n}", section="World", author="", date="2026-10-14", words=300, mins=2, url=f"https://example.org/{n}", html="<p>" + "word " * 100 + "</p>"), **kw)
pieces = [plain_piece(n) for n in range(7)]
pieces[5]["brief"] = True; pieces[6]["unit"] = ("post", "posts")
shown = [("Sat midday", "Wire", "Fed holds rates steady"), ("Sat am", "Wire", "Oil jumps on supply fears")]
edit = {"score": {}, "must": [1, 99, "x", 1, 5, 6, 0, 2, 3], "repeat": [{"id": 2, "of": "fed holds rates steady"}, {"id": 3, "of": "A headline never shown"}, {"id": 4, "of": "Oil jumps on supply fears"}, {"id": 0, "of": "Fed holds rates steady"}, "junk", {"id": 5, "of": "Fed holds rates steady"}]}
out = briefing.apply_edit(pieces, edit, shown)
assert sorted(a["title"] for a in out if a.get("must")) == ["Story 0", "Story 1", "Story 2"], "the first three valid, distinct, plain ids; briefs, lists and unknown ids are skipped"
assert [a["title"] for a in out if a.get("repeat")] == ["Story 4"], "a repeat needs a headline the earlier editions carried (copied), and never applies to a Must read, a brief or a list"
assert sum(1 for a in out if a.get("must")) == 3 == briefing.MUST_READ
assert not any(a.get("repeat") or a.get("must") for a in briefing.apply_edit([plain_piece(0), plain_piece(1)], "not json", shown)), "a bad reply changes nothing"
odd = briefing.apply_edit([plain_piece(0), plain_piece(1)], {"must": [[1, 2], {"id": 1}, None, 1], "same": [[[0], {"a": 1}, 0, 1]], "repeat": [{"id": [0], "of": "x"}]}, shown)
assert len(odd) == 1 and odd[0].get("must") is True, "unhashable or odd entries in the editor's reply are ignored, never fatal; the valid ids still count"
twin_a, twin_b = plain_piece(0, score=5), plain_piece(1, score=3, must=False)
out = briefing.apply_edit([twin_a, twin_b], {"same": [[0, 1]], "score": {"0": 5, "1": 9}, "must": [0]}, shown)
assert len(out) == 1 and out[0]["title"] == "Story 1" and out[0]["must"] is True, "a Must read mark follows its piece into the kept twin"
long_piece = plain_piece(9, words=3000, pub="", author_raw="", html="<p>" + "The firm raised money. " * 600 + "</p>")
assert not briefing.apply_edit([long_piece], {"repeat": [{"id": 0, "of": "Fed holds rates steady"}]}, shown)[0].get("repeat"), "an essay is never a repeat"
marked = [plain_piece(n, must=(n < 2)) for n in range(4)]
_, _, book = briefing.render(marked, [], now, "Morning", earlier=2)
assert book.count("Must read") == 6, "the word shows in the Contents line, on the front page and in the story's byline, for two pieces"
contents = book[book.index('id="toc"'):book.index("</section>", book.index('id="toc"'))]
assert contents.count(" · Must read") == 2 and "2 pieces that repeated a story from an earlier edition" in contents, "a word in the Contents, a count in the left-out note"
assert re.search(r'class="by">.*?</b>[^<]*min read · Must read', book), "the mark is a plain word in the byline"
prompts = []
briefing.ask_model = lambda prompt: prompts.append(prompt) or {"score": {}}
real_which = briefing.shutil.which; briefing.shutil.which = lambda _x: "/bin/x"
briefing.PROFILE = pathlib.Path(tempfile.mkdtemp()) / "p.md"; briefing.PROFILE.write_text("health")
briefing.ask_editor([plain_piece(n) for n in range(3)], shown)
assert "Sat midday | Wire | Fed holds rates steady" in prompts[0] and '"must"' in prompts[0] and '"repeat"' in prompts[0] and "adds no new fact" in prompts[0], "the editor sees the earlier headlines and is told what a repeat is"
briefing.ask_editor([plain_piece(n) for n in range(3)]); assert "(none)" in prompts[1]
del briefing.ask_model; briefing.shutil.which = real_which
import importlib  # noqa: E402

class RecordsTmp:
    pass
with tempfile.TemporaryDirectory() as tmp:
    briefing.EDITIONS = pathlib.Path(tmp) / "editions"
    utc = datetime.datetime(2026, 10, 24, 9, 0, tzinfo=datetime.timezone.utc)
    rec = briefing.edition_record([plain_piece(1, score=7, must=True, summary="Fed holds rates steady. Markets expected a cut."), plain_piece(2, brief=True), plain_piece(3, unit=("post", "posts"))], utc, "briefing-2026-10-24-am", "https://a.example/x", "Morning")
    other = briefing.edition_record([plain_piece(4, html="<p>" + "A long opening paragraph about the story. " * 6 + "</p>")], utc, "x", "", "Morning")["pieces"][0]
    assert other["line"].startswith("A long opening paragraph") and other["line"].endswith("…"), "a piece the editor did not feature still records its opening line"
    assert [p["title"] for p in rec["pieces"]] == ["Story 1"] and rec["pieces"][0]["must"] and rec["pieces"][0]["line"] == "Fed holds rates steady.", "only real pieces are remembered"
    briefing.save_edition(rec)
    old = dict(rec, slug="old", at=(utc - datetime.timedelta(days=16)).isoformat()); briefing.EDITIONS.mkdir(exist_ok=True); (briefing.EDITIONS / "old.json").write_text(json.dumps(old))
    (briefing.EDITIONS / "junk.json").write_text("not json")
    briefing.save_edition(dict(rec, slug="briefing-2026-10-24-midday", at=(utc + datetime.timedelta(hours=8)).isoformat(), edition="Midday"))
    assert sorted(p.name for p in briefing.EDITIONS.glob("*.json")) == ["briefing-2026-10-24-am.json", "briefing-2026-10-24-midday.json", "junk.json"], "records older than 15 days are deleted"
    got = briefing.load_editions(utc + datetime.timedelta(hours=20), 48)
    assert [r["slug"] for r in got] == ["briefing-2026-10-24-am", "briefing-2026-10-24-midday"] and briefing.load_editions(utc + datetime.timedelta(hours=80), 48) == [], "the last 48 hours, oldest first; a junk record is skipped"
    heads = briefing.shown_headlines(got)
    assert heads[0] == ("Sat morning", "Paper 1", "Story 1"), heads
    junk_rec = dict(rec, pieces=[{"url": "https://z.example/1"}, "not a piece"])
    assert briefing.drop_shown([plain_piece(5)], [junk_rec])[1] == 0, "a damaged record never fails the run"
    assert briefing.shown_headlines([dict(rec, pieces=[{"title": "No source"}, {"source": "No title"}, "junk"])]) == [(briefing.shown_headlines([rec])[0][0], "", "No source")], "a piece without a source or title in a damaged record is skipped, never fatal"
    kept, dropped = briefing.drop_shown([plain_piece(1, url="https://other.example/y"), plain_piece(8, url="https://example.org/1"), plain_piece(9), plain_piece(2, brief=True, title="Story 1"), plain_piece(3, url="", title="Story 1")], got)
    assert [a["title"] for a in kept] == ["Story 1", "Story 9", "Story 1"] and kept[0]["url"] == "https://other.example/y" and dropped == 2, "the same link is dropped, or the same title when the piece has no link; a fixed title with its own link and a brief group stay"

# The Sunday digest: built from the week's records, no fetching; one extra run for the market moves.
week_utc = datetime.datetime(2026, 10, 25, 3, 0, tzinfo=datetime.timezone.utc)
def wrecord(day, slot, titles):
    at = datetime.datetime(2026, 10, day, 3 if slot == "am" else 11, 0, tzinfo=datetime.timezone.utc)
    pcs = [dict(title=t, source=f"Src {t[:1]}", author="An Author", section=sec, url=f"https://example.org/{day}{slot}{i}", mins=4, score=sc, must=m, line=f"Line about {t}.") for i, (t, sec, sc, m) in enumerate(titles)]
    return dict(slug=f"briefing-2026-10-{day}-{slot}", url=f"https://a.example/{day}{slot}", edition="Morning" if slot == "am" else "Midday", at=at.isoformat(), pieces=pcs)
week = [wrecord(20, "am", [("Alpha essay", "Business", 9, True), ("Beta note", "World", 3, False), ("Semafor roundup", "World", 10, True), ("Weekly Longreads + Open Thread", "Business", 10, False)]),
        wrecord(22, "am", [("Gamma deal", "Business", 7, False), ("Alpha essay", "Business", 6, False), ("Oil rose 5 percent after supply fears", "Business", 5, False),
                           ("Bonds rallied 25 bp as yields fell", "Markets & Macro", 2, False)] + [(f"Filler {n}", "Life", 1, False) for n in range(12)])]
moves_seen = []
briefing.ask_model = lambda prompt: moves_seen.append(prompt) or {"moves": ["Oil rose 5 percent on supply fears.", "Gold fell after the Fed held.", "Bonds rallied 25 bp.", "Invented 99 percent surge in shares.", "x"]}
real_which = briefing.shutil.which; briefing.shutil.which = lambda _x: "/bin/x"
digest = briefing.build_week(week, week_utc)
briefing.shutil.which = real_which
assert len(digest) == 1 and digest[0]["section"] == "The week" and digest[0]["unit"] == ("item", "items"), digest
body = digest[0]["html"]
assert [h for h in re.findall(r"<h2 class='xsub'>([^<]+)</h2>", body)] == ["The week's best pieces", "Key market moves of the week"], "two parts in order"
best = body[:body.index("Key market moves")]
assert best.count("<p class='follow'>") == 10 and best.index("Alpha essay") < best.index("Gamma deal") < best.index("Beta note") and best.count(">Alpha essay<") == 1 and "Must read" in best, "the 10 best pieces by score and Must read, a repeated title once"
assert "Semafor roundup" not in best and "Longreads" not in best, "briefings and roundups are never among the week's best pieces"
assert "<b>Src A</b> · An Author" in best and "<b>Src B</b> · An Author" in best, "the publication in bold, then the journalist"
assert "Filler 9" not in best and "https://example.org/20am0" in best and body.count("<strong>") == 10, "only 10, linked to the piece"
assert "Oil rose 5 percent" in body and "Bonds rallied 25 bp" in body and "Invented 99" not in body and "Gold fell" in body, "market moves keep only figures the items state"
assert len(moves_seen) == 1 and "untrusted" in moves_seen[0] and "Alpha essay" in moves_seen[0] and "Filler" not in moves_seen[0], "one run, Business pieces only"
briefing.ask_model = lambda prompt: None
briefing.shutil.which = lambda _x: "/bin/x"; nomoves = briefing.build_week(week, week_utc)[0]["html"]; briefing.shutil.which = real_which
assert "Key market moves" not in nomoves and "The week's best pieces" in nomoves, "a failed moves run shows nothing"
del briefing.ask_model
assert briefing.build_week([wrecord(20, "am", [])], week_utc) == [] and briefing.build_week([], week_utc) == [], "nothing to show, no section"
print("briefing source and cleaning checks passed")


def roundup(id, author, heads, source="Pharmalittle + Health Tech (STAT+)", published="2026-01-01T06:00:00.000000Z", extra="", section="Biopharma"):
    items = "".join(f"<h2><a href='https://example.org/{id}/{n}?utm_source=nl'>{h}</a></h2><p>{' '.join(['A sentence of summary about it.'] * 30)}</p>" for n, h in enumerate(heads))
    return dict(entry, id=id, title=f"Issue {id} {heads[0]}", author=author, _source=source, _section=section, published=published, content=items + extra)


stat = lambda id, series, heads, hour: roundup(id, f"STAT | {series}", heads, published=f"2026-01-01T{hour}:00:00.000000Z")
H = ["Launch prices for new drugs dip slightly but remain high", "Why I wish you didn't want to see the Holmes documentary",
     "Dana-Farber and Beth Israel to begin construction of a new cancer hospital", "Resident physicians may lose work hour protections"]
# STAT's list series are not pieces any more: their items are headlines under the publication's name. The written series stays a piece.
arts, _, heads, _ = briefing.build_articles([
    stat(10, "Daily Recap", H[:3], "01"),
    stat(11, "STAT+ Today", H[1:], "02"),
    stat(12, "Pharmalittle", H[:3], "03"),
    stat(13, "Pharmalot", ["Muted lister headline number one", "Muted lister headline number two", "Muted lister headline number three"], "06"),
    stat(14, "Weekend Reads", ["Muted weekend headline number one", "Muted weekend headline number two"], "07"),
    stat(15, "The Readout", ["Roche goes beyond licensing in a new deal", "Beam alleges a Chinese company stole its technology"], "05"),
])
assert [a["title"] for a in arts if not a["daily"]] == [] and all(a["daily"] for a in arts), "STAT's list series are daily newsletters, never articles"
assert {h["title"] for h in heads} >= set(H) | {"Muted lister headline number one", "Muted weekend headline number two"} and {h["source"] for h in heads} == {"STAT"} and all(h["hint"] == "Biotech & Health" for h in heads), "every list series gives headlines"
assert next(h for h in heads if h["title"] == H[0])["url"] == "https://example.org/10/0", "a headline keeps its link without the tracking query"
assert len(briefing.H.unique(heads)) < len(heads), "the same headline in several mailings is one"

# The other roundups (WSJ What's News, the Economist's briefs ...) give headlines too, under their own publication's name; any piece made of them is a daily newsletter.
eco = roundup(20, "The Economist", ["Elon Musk ordered the Starlink slowdown that hindered Kyiv", "Another unrelated Economist headline today"], source="The Economist", published="2026-01-01T07:00:00.000000Z", section="World")
wsj = roundup(21, "WSJ", ["Elon Musk ordered the Starlink slowdown that hindered Kyiv"], source="WSJ What's News", published="2026-01-01T06:30:00.000000Z", section="Business")
arts, _, heads, _ = briefing.build_articles([wsj, eco])
assert all(a["daily"] for a in arts) and sorted({(h["source"], h["hint"]) for h in heads}) == [("The Economist", "World"), ("The Wall Street Journal", "Business")], heads

# A written piece that repeats a linked line from an earlier piece keeps its fresh ones; every other roundup rule is the headline pool's.
link = lambda h: f"<h2><a href='https://example.org/{h.split()[0].lower()}?utm=1'>{h}</a></h2>"
body = "<p>" + " ".join(["More reporting follows here."] * 60) + "</p>"
arts, _, _, _ = briefing.build_articles([dict(entry, id=22, title="W", _source="Some Writer", content=link("Shared story headline words here") + body),
                                      dict(entry, id=23, title="E", _source="Another Writer", published="2026-01-01T08:00:00.000000Z", content=link("Shared story headline words here") + link("Fresh story headline words here") + body)])
by = {a["id"]: a for a in arts}
assert 22 in by and 23 in by and "Shared story" in by[22]["html"] and "Shared story" not in by[23]["html"] and "Fresh story" in by[23]["html"], "one repeated linked line goes, both pieces stay"

# A newsletter that is mostly a run of short headline blocks is a headline list whatever the publication; a written one, or a list with a long written intro, stays a piece.
def block(n, words=12): return f"<h2><a href='https://example.org/b{n}'>Headline number {n} about something</a></h2><p>{' '.join(f'word{n}x{i}' for i in range(words))}</p><p>By Reporter {n}</p>"
listing = "".join(block(n) for n in range(12))
essay = "".join(block(n, 120) for n in range(8))
letter = "<p>" + " ".join(["A written opening from the editor."] * 90) + "</p>" + listing
assert briefing.R.headline_list(listing) and "12 headline blocks" in briefing.R.headline_list(listing)
assert not briefing.R.headline_list(essay) and not briefing.R.headline_list(letter) and not briefing.R.headline_list(block(1) * 4), "written, long intro, or fewer than five blocks"
other = dict(entry, id=50, title="Weekly links", author="Some Editor", _source="Some Weekly", _section="World", content=listing)
written = dict(entry, id=51, title="Weekly essays", author="Some Editor", _source="Some Weekly", _section="World", content=essay)
arts, _, heads, _ = briefing.build_articles([other, written])
assert [a["id"] for a in arts if not a["daily"]] == [51] and len(heads) == 12 and heads[0]["source"] == "Some Weekly" and heads[0]["title"] == "Headline number 0 about something", ([a["id"] for a in arts], len(heads))
# Endpoints News items are headlines with their own link; a paid-source article read in full is never taken for a roundup, whatever the publication is called.
ep = dict(entry, id=60, title="Endpoints: Pfizer buys a biotech", url="https://endpoints.news/pfizer-buys/", _source="Endpoints News", _section="Biopharma", _direct=True, content="<p>" + "Pfizer will pay a lot. " * 20 + "</p>")
arts, _, heads, shorts = briefing.build_articles([ep])
assert arts == [] and shorts[0]["title"] == "Endpoints: Pfizer buys a biotech" and shorts[0]["section"] == "Biotech & Health" and heads[0]["title"] == "Endpoints: Pfizer buys a biotech" and heads[0]["url"] == "https://endpoints.news/pfizer-buys/" and heads[0]["source"] == "Endpoints News", heads
econ = dict(entry, id=61, title="Why the dollar is wobbling", author="The Economist", url="https://www.economist.com/finance-and-economics/2026/10/22/why-the-dollar-is-wobbling", _source="The Economist", _section="Markets & Macro", _fulltext="economist:x",
            content="".join(f"<p>{' '.join(f'Paragraph {n} sentence {i}: the dollar fell as traders weighed the cuts ahead.' for i in range(20))}</p>" for n in range(8)))
arts, _, heads, _ = briefing.build_articles([econ])
assert len(arts) == 1 and heads == [] and arts[0]["fulltext"] and arts[0]["section"] == "Markets & Macro" and arts[0]["words"] > 1200, "an Economist article read in full is a piece in its theme"
assert briefing.R.long_read(arts[0]), "and may carry the In short summary although the publication's name is on the roundup list"
print("briefing roundup rules passed")

# Kindle delivery: one send per edition, idempotent, skipped in dry-run, and never a cost to the edition. The HTTP call is mocked; nothing is mailed.
import base64, io, types  # noqa: E402
import urllib.error  # noqa: E402


class Clock(datetime.datetime):
    at = datetime.datetime(2026, 10, 24, 2, 30, tzinfo=datetime.timezone.utc)   # 04:30 in Cape Town: the morning edition

    @classmethod
    def now(cls, tz=None):
        return cls.at.astimezone(tz) if tz else cls.at


def http_error(code):
    return urllib.error.HTTPError(briefing.RESEND_URL, code, "x", {}, io.BytesIO(b'{"message":"nope"}'))


def run_edition(tmp, *argv, outcomes=(), key="re_test_key", feed=None, editor=None, ft_result=None, kindle_to="reader@kindle.example"):
    """Run main() against stubs. Returns the payloads the mocked Resend call received."""
    sent, queue = [], list(outcomes)

    def fake_post(payload, idempotency_key):
        sent.append((payload, idempotency_key))
        out = queue.pop(0) if queue else 200
        if isinstance(out, Exception):
            raise out
        return out

    def fake_documents(book, now, edition, pdf, epub):
        epub.write_bytes(b"fake epub")

    briefing.datetime = types.SimpleNamespace(datetime=Clock, timezone=datetime.timezone, timedelta=datetime.timedelta, date=datetime.date)
    briefing.STATE, briefing.OUTPUT = tmp / "state", tmp / "public"
    briefing.KINDLE_TO, briefing.KINDLE_FROM = kindle_to, "The Brief <briefing@mail.example>"
    briefing.KINDLE_SENT, briefing.KINDLE_FAILED = briefing.STATE / "kindle_sent", briefing.STATE / "kindle_failed"
    briefing.TRENDING_SEEN = briefing.STATE / "trending_seen"
    briefing.OUTPUT.mkdir(parents=True, exist_ok=True)
    briefing.RESEND_KEY = key
    briefing.EDITIONS, briefing.WEEKLY_SEEN = briefing.STATE / "editions", briefing.STATE / "weekly_seen"
    run_edition.n = getattr(run_edition, "n", 0) + 1
    stubs = dict(fetch_reader=lambda since: [dict(entry, title=f"{entry['title']} number {run_edition.n} ", url=f"{entry['url']}/{run_edition.n}")] if feed is None else feed, fetch_direct=lambda since: [],
                 fetch_forefront=lambda since, record=True: [], fetch_fulltext=lambda since, entries, utc, now, edition: ft_result or briefing.FT.Result([], [], [], {}), fill_full_text=lambda entries: None, ask_editor=editor or (lambda arts, shown=(): None),
                 fetch_trending=lambda day: [],
                 documents=fake_documents, resend_post=fake_post)
    saved = {k: getattr(briefing, k) for k in stubs} | {"sleep": briefing.time.sleep, "argv": sys.argv}
    for k, v in stubs.items():
        setattr(briefing, k, v)
    briefing.time.sleep = lambda s: None
    sys.argv = ["briefing.py", *argv]
    try:
        briefing.main()
    finally:
        for k, v in saved.items():
            if k == "sleep":
                briefing.time.sleep = v
            elif k == "argv":
                sys.argv = v
            else:
                setattr(briefing, k, v)
    return sent


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    sent = run_edition(tmp, "--since-hours", "24")
    assert len(sent) == 1, sent
    payload, idem = sent[0]
    assert payload["from"] == "The Brief <briefing@mail.example>" and payload["to"] == ["reader@kindle.example"], payload
    assert payload["subject"] == "The Brief, morning, 24 October 2026", payload["subject"]
    att, = payload["attachments"]
    assert att["filename"] == "brief-2026-10-24-am.epub" and base64.b64decode(att["content"]) == b"fake epub", att["filename"]
    assert idem == "kindle-brief-2026-10-24-am.epub"
    assert (tmp / "state/kindle_sent").read_text() == "brief-2026-10-24-am.epub\n" and not (tmp / "state/kindle_failed").exists()

    again = run_edition(tmp, "--since-hours", "24")
    assert [p["attachments"][0]["filename"] for p, _ in again] == ["brief-2026-10-24-am-2.epub"], "a rebuild published to a new path sends its own EPUB, named after that path"
    assert (tmp / "state/kindle_sent").read_text() == "brief-2026-10-24-am.epub\nbrief-2026-10-24-am-2.epub\n"
    briefing.send_kindle(tmp / "public/briefing-2026-10-24-am/briefing.epub", Clock.at.astimezone(briefing.TZ), "Morning", "briefing-2026-10-24-am")
    assert (tmp / "state/kindle_sent").read_text().count("brief-2026-10-24-am.epub") == 1, "one path is never sent twice"

    Clock.at = datetime.datetime(2026, 10, 24, 10, 30, tzinfo=datetime.timezone.utc)      # 12:30: the midday edition is a new edition
    sent = run_edition(tmp, "--since-hours", "24")
    assert [p["subject"] for p, _ in sent] == ["The Brief, midday, 24 October 2026"]
    assert sent[0][0]["attachments"][0]["filename"] == "brief-2026-10-24-midday.epub"

    Clock.at = datetime.datetime(2026, 10, 25, 2, 30, tzinfo=datetime.timezone.utc)
    published = len(list(briefing.OUTPUT.iterdir()))
    assert run_edition(tmp, "--since-hours", "24", "--dry-run") == [], "a dry run never sends"
    assert not (tmp / "state/kindle_failed").exists() and "2026-10-25" not in (tmp / "state/kindle_sent").read_text()
    assert len(list(briefing.OUTPUT.iterdir())) == published, "a dry run publishes nothing"

    briefing.SEND_PAUSES = (0, 0)
    sent = run_edition(tmp, "--since-hours", "24", outcomes=[http_error(503), urllib.error.URLError("reset"), 200])
    assert len(sent) == 3 and all(i == "kindle-brief-2026-10-25-am.epub" for _, i in sent), "two retries reuse one idempotency key"
    assert "brief-2026-10-25-am.epub" in (tmp / "state/kindle_sent").read_text()

    Clock.at = datetime.datetime(2026, 10, 26, 2, 30, tzinfo=datetime.timezone.utc)
    sent = run_edition(tmp, "--since-hours", "24", outcomes=[http_error(503)] * 3)
    assert len(sent) == 3, "a transient error is tried three times in all"
    failed = (tmp / "state/kindle_failed").read_text()
    assert "The Brief, morning, 26 October 2026 did not reach your Kindle" in failed and "re_test_key" not in failed, failed
    assert (tmp / "state/last_run").exists() and (tmp / "state/editions.tsv").exists()
    assert "brief-2026-10-26-am.epub" not in (tmp / "state/kindle_sent").read_text()
    assert any(p.name == "briefing-2026-10-26-am" for p in briefing.OUTPUT.iterdir()), "the edition is published even though the send failed"

    Clock.at = datetime.datetime(2026, 10, 26, 10, 30, tzinfo=datetime.timezone.utc)
    assert briefing.kindle_notice() == failed
    sent = run_edition(tmp, "--since-hours", "24", outcomes=[http_error(403)])
    assert len(sent) == 1, "a client error is not retried"
    page = (briefing.OUTPUT / "briefing-2026-10-26-midday/briefing.html").read_text()
    assert "did not reach your Kindle" in page and "The Brief, morning, 26 October 2026" in page, "the next edition says the last send failed"
    assert "nope" not in page and "re_test_key" not in page, "the published cover carries a short reason, not the response body"
    assert "midday, 26 October 2026 did not reach your Kindle (HTTP 403)." in (tmp / "state/kindle_failed").read_text()

    Clock.at = datetime.datetime(2026, 10, 27, 2, 30, tzinfo=datetime.timezone.utc)
    sent = run_edition(tmp, "--since-hours", "24")
    page = (briefing.OUTPUT / "briefing-2026-10-27-am/briefing.html").read_text()
    assert "midday, 26 October 2026 did not reach your Kindle" in page, "the failed midday send is reported once"
    assert not (tmp / "state/kindle_failed").exists()
    Clock.at = datetime.datetime(2026, 10, 27, 10, 30, tzinfo=datetime.timezone.utc)
    run_edition(tmp, "--since-hours", "24")
    # The full-text plug-in point: a piece it returns is an ordinary piece of its theme; every source it could not read is one plain line in the edition itself. The public hook remembers nothing.
    ft_piece = dict(entry, id=777, title="Mercuria challenges the Baltic Exchange in court", _source="Financial Times", author="Jane Roe", _section="Markets & Macro", _fulltext="ft:eedb7159-65df-45de-91f9-fde8de99e61c",
                    url="https://www.ft.com/content/eedb7159-65df-45de-91f9-fde8de99e61c", content="<p>" + " ".join(["The Baltic Exchange is being challenged."] * 60) + "</p>")
    run_edition(tmp, "--since-hours", "24", ft_result=briefing.FT.Result([ft_piece], [], [ft_piece["_fulltext"]], {}))
    published = max(briefing.OUTPUT.iterdir(), key=lambda p: p.stat().st_mtime_ns)
    page = (published / "briefing.html").read_text()
    assert "Mercuria challenges the Baltic Exchange in court" in page and "Financial Times" in page and "full text unavailable" not in page, "an FT article is a piece like any other"
    assert 'data-title="Markets &amp; Macro"' in page, "filed under its theme"
    assert not (tmp / "state/fulltext_seen").exists(), "the public hook keeps no memory of its own"
    run_edition(tmp, "--since-hours", "24", ft_result=briefing.FT.Result([], ["Source A full text unavailable: the plug-in could not read it.", "Source B full text unavailable: the plug-in could not read it."], [], {}))
    page = (max(briefing.OUTPUT.iterdir(), key=lambda p: p.stat().st_mtime_ns) / "briefing.html").read_text()
    assert page.count("Source A full text unavailable: the plug-in could not read it.") == 1 and page.count("Source B full text unavailable: the plug-in could not read it.") == 1 and page.count('class="left"') >= 2, "the edition says in one line each which full text is missing"
    assert "did not reach your Kindle" not in (briefing.OUTPUT / "briefing-2026-10-27-midday/briefing.html").read_text()

    Clock.at = datetime.datetime(2026, 10, 28, 2, 30, tzinfo=datetime.timezone.utc)
    assert run_edition(tmp, "--since-hours", "24", key="") == [], "without a key nothing is sent"
    assert "BRIEFING_RESEND_API_KEY is not set" in (tmp / "state/kindle_failed").read_text(), "a missing key is reported in the next edition"
    assert any(p.name == "briefing-2026-10-28-am" for p in briefing.OUTPUT.iterdir())
    briefing.KINDLE_FAILED.unlink()
    Clock.at = datetime.datetime(2026, 10, 28, 10, 30, tzinfo=datetime.timezone.utc)
    assert run_edition(tmp, "--since-hours", "24", kindle_to="") == [] and not (tmp / "state/kindle_failed").exists(), "no Kindle address: delivery is off, not a failure"
# Cross-edition memory and the Sunday digest, through main().
def edition_entry(n, title, **kw): return dict(entry, id=900 + n, title=title, url=f"https://example.org/e/{n}", **kw)
with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    seen_prompts = []
    def editor(arts, shown=()):
        seen_prompts.append((len(arts), list(shown)))
        return {"score": {str(i): 5 for i in range(len(arts))}, "must": [i for i, a in enumerate(arts) if "again" not in a["title"]][:3], "repeat": [{"id": i, "of": t} for i, a in enumerate(arts) for _, _, t in shown if "again" in a["title"]][:1]}
    Clock.at = datetime.datetime(2026, 10, 22, 2, 30, tzinfo=datetime.timezone.utc)
    run_edition(tmp, "--since-hours", "24", feed=[edition_entry(1, "Fed holds rates steady"), edition_entry(2, "Chip firm raises 5 billion")], editor=editor)
    page = (briefing.OUTPUT / "briefing-2026-10-22-am/briefing.html").read_text()
    assert page.count("Must read") >= 2 and seen_prompts[-1] == (2, []), "the first edition has nothing to repeat; the editor marks Must read"
    assert len(list((tmp / "state/editions").glob("*.json"))) == 1, "a published edition leaves a record"
    Clock.at = datetime.datetime(2026, 10, 22, 10, 30, tzinfo=datetime.timezone.utc)
    run_edition(tmp, feed=[dict(edition_entry(3, "Fed holds rates steady"), url="https://example.org/e/1"), edition_entry(4, "Fed holds rates again, markets shrug"), edition_entry(5, "A new story about biotech funding")], editor=editor)
    page = (briefing.OUTPUT / "briefing-2026-10-22-midday/briefing.html").read_text()
    assert "Fed holds rates steady" not in page.split('id="toc"', 1)[1].split("</section>", 1)[0] and "again, markets shrug" not in page and "A new story about biotech funding" in page, "a story the morning carried does not come back, nor its repeat"
    assert "2 pieces that repeated a story from an earlier edition" in page, "the left-out note counts both"
    assert [h for _, _, h in seen_prompts[-1][1]] == ["Fed holds rates steady", "Chip firm raises 5 billion"] and seen_prompts[-1][0] == 2, "the editor is shown the morning's headlines and the deterministic repeat never reaches it"
    before = sorted(p.name for p in (tmp / "state/editions").glob("*.json"))
    Clock.at = datetime.datetime(2026, 10, 22, 11, 0, tzinfo=datetime.timezone.utc)
    run_edition(tmp, "--since-hours", "30", "--dry-run", feed=[dict(edition_entry(3, "Fed holds rates steady"), url="https://example.org/e/1")], editor=editor)
    rebuilt = (tmp / "state/briefing-2026-10-22-midday-dry-run.html").read_text()
    assert "Fed holds rates steady" in rebuilt.split('id="toc"', 1)[1].split("</section>", 1)[0] and "repeated a story" not in rebuilt, "a rebuild of a window that already has records does not see its own pieces as repeats"
    Clock.at = datetime.datetime(2026, 10, 22, 11, 30, tzinfo=datetime.timezone.utc)
    run_edition(tmp, "--since-hours", "24", "--dry-run", feed=[edition_entry(6, "Dry run only story")], editor=editor)
    assert sorted(p.name for p in (tmp / "state/editions").glob("*.json")) == before, "a dry run leaves no record"
    run_edition(tmp, "--since-hours", "2", feed=[edition_entry(7, "Rebuilt slot story")], editor=editor)
    names = sorted(p.name for p in (tmp / "state/editions").glob("*.json"))
    assert "briefing-2026-10-22-midday.json" in names and "briefing-2026-10-22-midday-2.json" in names and len(names) == len(before) + 1, "a rebuild of a published slot gets its own record and never overwrites the real one"

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    Clock.at = datetime.datetime(2026, 10, 25, 2, 30, tzinfo=datetime.timezone.utc)      # Sunday 04:30 in Cape Town
    (tmp / "state/editions").mkdir(parents=True)
    for r in week: (tmp / "state/editions" / f"{r['slug']}.json").write_text(json.dumps(r))
    briefing.market_moves = lambda records: ["Oil rose 5 percent on supply fears."]
    run_edition(tmp, "--since-hours", "24", feed=[edition_entry(30, "Sunday story")])
    page = (briefing.OUTPUT / "briefing-2026-10-25-am/briefing.html").read_text()
    assert re.findall(r'<section class="sec[^"]*" id="s\d+" data-title="([^"]+)"', page)[:1] == ["The week"], "Sunday morning opens with the week"
    assert "The week&#x27;s best pieces" in page or "The week's best pieces" in page, "the digest is in the edition"
    assert (tmp / "state/weekly_seen").read_text().split() == ["2026-10-25"], "recorded so a rebuild the same day does not repeat it"
    Clock.at = datetime.datetime(2026, 10, 25, 2, 45, tzinfo=datetime.timezone.utc)
    run_edition(tmp, "--since-hours", "24", feed=[edition_entry(31, "Another Sunday story")])
    again = (briefing.OUTPUT / "briefing-2026-10-25-am-2/briefing.html").read_text()
    assert 'data-title="The week"' not in again, "once per Sunday"
    real_week = briefing.build_week
    briefing.build_week = lambda *a: (_ for _ in ()).throw(KeyError("title"))
    Clock.at = datetime.datetime(2026, 11, 8, 2, 30, tzinfo=datetime.timezone.utc)      # Sunday with a damaged record
    try: run_edition(tmp, "--since-hours", "24", feed=[edition_entry(35, "Damaged record story")])
    finally: briefing.build_week = real_week
    assert (briefing.OUTPUT / "briefing-2026-11-08-am/briefing.html").exists() and 'data-title="The week"' not in (briefing.OUTPUT / "briefing-2026-11-08-am/briefing.html").read_text(), "a digest that breaks never costs the edition"
    Clock.at = datetime.datetime(2026, 10, 26, 2, 30, tzinfo=datetime.timezone.utc)      # Monday
    run_edition(tmp, "--since-hours", "24", feed=[edition_entry(32, "Monday story")])
    assert 'data-title="The week"' not in (briefing.OUTPUT / "briefing-2026-10-26-am/briefing.html").read_text(), "only on Sundays"
    Clock.at = datetime.datetime(2026, 11, 1, 10, 30, tzinfo=datetime.timezone.utc)      # Sunday midday
    run_edition(tmp, "--since-hours", "24", feed=[edition_entry(33, "Sunday midday story")])
    assert 'data-title="The week"' not in (briefing.OUTPUT / "briefing-2026-11-01-midday/briefing.html").read_text(), "the morning edition only"
    Clock.at = datetime.datetime(2026, 10, 27, 2, 30, tzinfo=datetime.timezone.utc)
    run_edition(tmp, "--since-hours", "24", "--weekly", "--dry-run", feed=[edition_entry(34, "Forced story")])
    assert 'data-title="The week"' in (tmp / "state/briefing-2026-10-27-am-dry-run.html").read_text() and not (tmp / "state/weekly_seen").read_text().count("2026-10-27"), "--weekly previews it in a dry run without recording it"
# A summary run that breaks never costs the edition.
with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    Clock.at = datetime.datetime(2026, 11, 3, 2, 30, tzinfo=datetime.timezone.utc)
    real_add = briefing.add_summaries
    briefing.add_summaries = lambda arts: (_ for _ in ()).throw(KeyError("words"))
    try: run_edition(tmp, "--since-hours", "24")
    finally: briefing.add_summaries = real_add
    assert (briefing.OUTPUT / "briefing-2026-11-03-am/briefing.html").exists(), "the edition is published without summaries"
print("briefing kindle delivery passed")

promo = dict(_source="The Economist", author="The Economist", content="<p>The Economist</p><p>Also: AI is upending the porn industry</p><p>October 24th 2026</p><p>The Economist This Week</p><p>Saturday edition</p>" + "<img src='x.jpg'>" * 25)
brief = dict(_source="The Economist", author="The Economist", content="<p>The World in Brief</p><p>Putin agrees to peace talks.</p>")
elsewhere = dict(_source="Semafor", author="Semafor", content="<p>Ahead of The Economist This Week, a note.</p>")
assert briefing.R.muted(promo), "The Economist This Week promo is muted"
assert not briefing.R.muted(brief), "other Economist newsletters are kept"
assert not briefing.R.muted(elsewhere), "the opening mute applies only to its own publication"
for receipt in ("Your payment receipt from Health API Guy #YQSWIJ2U-0002", "Your receipt from Stratechery", "Receipt for your payment"):
    assert briefing.R.admin(dict(title=receipt, author="Health API Guy", content="<p>Amount paid $10</p>")), receipt
assert not briefing.R.admin(dict(title="Hospitals receipt of federal funds slows", author="STAT", content="<p>x</p>")), "a story about receipts is journalism"
# Every piece says where it comes from (Andrea, 30 Oct 2026): "<b>Publisher</b> · Newsletter · Type, Author", the newsletter's name out of the title.
L = lambda **kw: briefing.label(dict(dict(source="", author="", author_raw="", title="", html="<p>x</p>", section="World", daily=False, words=500, published="2026-10-29T10:00:00.000000Z"), **kw))
multi = "".join(f"<h2>Story {n}</h2><p>" + "words here " * 30 + "</p>" for n in range(4))
cases = [
    (dict(source="The Economist · US in Brief", author_raw="The Economist", title="A fishy campaign in Alaska", daily=True, html=multi), ("The Economist", "US in Brief", "Briefing", "A fishy campaign in Alaska", "")),
    (dict(source="Semafor", author_raw="Semafor Flagship", title="Incomplete and contested", daily=True, html=multi), ("Semafor", "Flagship", "Briefing", "Incomplete and contested", "")),
    (dict(source="Axios", author_raw="Dan Primack", author="Dan Primack", title="Axios Pro Rata: Weil winds down", daily=True, html=multi), ("Axios", "Pro Rata", "Briefing", "Weil winds down", "Dan Primack")),
    (dict(source="Bloomberg", author_raw="Bloomberg", title="The AI numbers roll in", daily=True, html=multi, published="2026-10-28T21:48:00.000000Z"), ("Bloomberg", "Evening Briefing", "Briefing", "The AI numbers roll in", "")),
    (dict(source="Bloomberg", author_raw="Bloomberg", title="Netanyahu gains the edge", daily=True, html=multi, published="2026-10-28T11:06:00.000000Z"), ("Bloomberg", "Morning Briefing", "Briefing", "Netanyahu gains the edge", "")),
    (dict(source="Bloomberg", author_raw="Matt Levine at Bloomberg Opinion", author="Matt Levine at Bloomberg Opinion", title="Money Stuff: Run on the Law Firm", section="Long reads", words=4000), ("Bloomberg", "Money Stuff", "Essay", "Run on the Law Firm", "Matt Levine")),
    (dict(source="Bloomberg", author_raw="Bloomberg Odd Lots", author="Bloomberg Odd Lots", title="Maybe Wall Street has never been 'AI-pilled'", section="Long reads"), ("Bloomberg", "Odd Lots", "Essay", "Maybe Wall Street has never been 'AI-pilled'", "")),
    (dict(source="The Wall Street Journal", author_raw="WSJ Markets P.M.", title="Fed Sets Stage for December", daily=True, html=multi), ("The Wall Street Journal", "Markets P.M.", "Briefing", "Fed Sets Stage for December", "")),
    (dict(source="The Wall Street Journal", author_raw="Spencer Jakab, WSJ", author="Spencer Jakab, WSJ", title="Markets A.M.: What Big Oil Tells Us", daily=True, html=multi), ("The Wall Street Journal", "Markets A.M.", "Briefing", "What Big Oil Tells Us", "Spencer Jakab")),
    (dict(source="STAT", author_raw="Mario | Health Tech", author="Mario Aguilar", title="The EPIC investigation, and a Teladoc surprise", section="Biotech & Health"), ("STAT", "Health Tech", "Article", "The EPIC investigation, and a Teladoc surprise", "Mario Aguilar")),
    (dict(source="STAT", author_raw="STAT | Morning Rounds", title="Is Abdul El-Sayed Democrats' answer?", daily=True, html=multi), ("STAT", "Morning Rounds", "Briefing", "Is Abdul El-Sayed Democrats' answer?", "")),
    (dict(source="Financial Times", author_raw="FT Briefing", title="Markets afternoon briefing: John Healey avoids bond market", daily=True, html=multi), ("Financial Times", "Markets afternoon briefing", "Briefing", "John Healey avoids bond market", "")),
    (dict(source="Financial Times", author_raw="FirstFT Americas", title="End of the road for Weil", daily=True, html=multi), ("Financial Times", "FirstFT", "Briefing", "End of the road for Weil", "")),
    (dict(source="Fintech Brainfood (beehiiv)", author_raw="Brainfood by Simon Taylor", author="Brainfood by Simon Taylor", title="Exclusive: Ramp CEO", section="Long reads"), ("Fintech Brainfood", "Brainfood", "Essay", "Exclusive: Ramp CEO", "Simon Taylor")),
    (dict(source="Financial Times", author="Michael Acton", title="Intel shares fall 22%", fulltext=True), ("Financial Times", "", "Article", "Intel shares fall 22%", "Michael Acton")),
    (dict(source="Stratechery", author_raw="Ben Thompson", author="Ben Thompson", title="An Interview with Palantir CTO", section="Long reads"), ("Stratechery", "", "Essay", "An Interview with Palantir CTO", "Ben Thompson")),
]
for kw, want in cases:
    got = L(**kw)
    assert (got["publisher"], got["series"], got["kind"], got["title"], briefing.by_author(got)) == want, (kw["title"], (got["publisher"], got["series"], got["kind"], got["title"], briefing.by_author(got)))
assert briefing.byline(L(source="Semafor", author_raw="Semafor Flagship", title="Incomplete", daily=True, html=multi)) == "<b>Semafor</b> · Flagship · Briefing"
assert briefing.byline(L(source="Axios", author_raw="Dan Primack", author="Dan Primack", title="Axios Pro Rata: Weil", daily=True, html=multi)) == "<b>Axios</b> · Pro Rata · Briefing · Dan Primack"
assert briefing.byline(dict(source="X", author="", title="20 posts", unit=("post", "posts"))) == "<b>X</b>", "a list keeps its plain byline"
assert briefing.R.admin(dict(title="Sign up now for STAT+ Email Alerts", author="STAT+", content="<p>x</p>")), "a sign-up promotion is admin mail"
once = L(source="Bloomberg", author_raw="Bloomberg Odd Lots", author="Bloomberg Odd Lots", title="Credit", section="Long reads"); again = briefing.label(once)
assert again is once and (again["series"], briefing.by_author(again)) == ("Odd Lots", ""), "labelling twice changes nothing"
assert L(source="Bloomberg", author_raw="Bloomberg", title="Fed holds rates", fulltext=True)["series"] == "", "only a Bloomberg daily newsletter is a Morning or Evening Briefing"
assert L(source="Bloomberg", author_raw="Bloomberg News", title="Fed holds rates")["series"] == "", "Bloomberg News names no newsletter"
assert briefing.drop_shown([dict(title="FirstFT: Netanyahu leads", url="", source="Financial Times")], [dict(pieces=[dict(title="Netanyahu leads", url="")])])[0] == [], "a newsletter's name in front of a title does not make it new"
print("Economist This Week mute checks passed")
