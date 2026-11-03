#!/usr/bin/env python3
"""Checks for the Briefing's front page, "The day in two minutes": what is selected, how it is ordered and linked, the ten-line cap, and that nothing on it is written by anyone but the
generated summary and the ranking run."""
import datetime
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
JOB = ROOT / "briefing"
try:
    import bs4  # noqa: F401
    import lxml  # noqa: F401
except ImportError:
    print("briefing front page checks skipped: beautifulsoup4/lxml not installed")
    sys.exit(0)
sys.path.insert(0, str(JOB))
import os  # noqa: E402
os.environ.setdefault("BRIEFING_TZ", "Africa/Johannesburg")  # the checks were written for a Cape Town reader: Morning before 11:00 local time
import briefing  # noqa: E402
import front as F  # noqa: E402
import headlines as H  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

now = datetime.datetime(2026, 10, 26, 7, 15, tzinfo=briefing.TZ)
body = "<p>" + "word " * 100 + "</p>"
def piece(title, section="World", score=5, **kw):
    return dict(dict(title=title, source=f"Paper {title[:1]}", section=section, author="", date="2026-10-26", words=300, mins=2, url=f"https://example.org/{title.replace(' ', '-')}", html=body, score=score), **kw)
def line(title, theme="World", score=5, why="", source="Wire", **kw):
    return dict(dict(title=title, url=f"https://wire.example/{title.replace(' ', '-')}", source=source, theme=theme, score=score, why=why, blurb="", pos=0), **kw)
def lists(*rows):
    out = []
    for theme in dict.fromkeys(r["theme"] for r in rows): out.append(H.list_piece(theme, [r for r in rows if r["theme"] == theme], "2026-10-26"))
    return out
def front(arts):
    """Render, then read the front page back from the HTML: [(group, [(text, href, small print)])]."""
    _, _, book = briefing.render([a for a in arts if not a.get("lines")], [], now, "Morning", heads=[a for a in arts if a.get("lines")])
    if 'id="today"' not in book: return book, []
    today = BeautifulSoup(book[book.index('id="today"'):book.index('id="toc"')], "lxml")
    groups = []
    for el in today.select(".fgrp, p.fitem"):
        if "fgrp" in el.get("class"): groups.append((el.get_text(), []))
        else: groups[-1][1].append((el.a.get_text(), el.a["href"], el.select_one(".fsrc").get_text(), el.select_one(".fwhy").get_text() if el.select_one(".fwhy") else ""))
    return book, groups

# ------------------------------------------------------------------ the why clause: a short, plain clause that states nothing the headline does not
src = "Fed holds rates at 5.25% for a third meeting. Officials cite sticky inflation."
assert H.clean_why("It keeps borrowing costs high for longer.", src) == "It keeps borrowing costs high for longer"
assert H.clean_why("  keeps costs high — for longer", src) == "Keeps costs high, for longer", "a dash becomes a comma; the first letter is capital"
assert H.clean_why("Rates stay at 5.25% for now.", src) == "Rates stay at 5.25% for now", "a figure the headline states is fine"
assert H.clean_why("Rates stay at 4.75% for now.", src) == "", "a figure the headline never states is an invention"
assert H.clean_why("Why it matters to you is a long story that keeps going on and on and on", src) == "", "more than 14 words is not a short clause"
assert H.clean_why("Matters.", src) == "" and H.clean_why(["x"], src) == "" and H.clean_why(None, src) == "", "too short or not text"
assert H.clean_why("See https://x.example for why it matters", src) == "" and H.clean_why("It matters [1] a lot to markets", src) == "", "no link or markup"

# The ranking run carries it, for the headlines it scores 7 or more only.
pool = [dict(title=f"Headline {n} about the economy", url=f"https://wire.example/{n}", blurb=f"Blurb {n} with 3 points", source="Wire", pos=n, hint="World") for n in range(4)]
reply = {"items": {"0": {"section": "World", "score": 9, "why": "It moves oil prices and shipping costs."}, "1": {"section": "AI", "score": 6, "why": "Low scorer must not carry one anyway."},
                   "2": {"section": "World", "score": 8, "why": "It adds 99 new rules."}, "3": {"section": "World", "score": 8}}}
asked = []
ranked = H.rank(pool, lambda prompt: asked.append(prompt) or reply, "")
why = {x["title"]: x["why"] for x in ranked}
assert why == {"Headline 0 about the economy": "It moves oil prices and shipping costs", "Headline 1 about the economy": "", "Headline 2 about the economy": "", "Headline 3 about the economy": ""}, why
assert len(asked) == 1 and '"why"' in asked[0], "the ranking run already being made is asked for it: no extra model call"
assert all(x["why"] == "" for x in H.rank(pool, None, "")), "without the model there is no clause"

# ------------------------------------------------------------------ a full article: the first sentence of its summary, or its headline
assert F.lead("The firm raised $2 billion. It will spend it on chips.") == "The firm raised $2 billion." and F.lead("Dr. Smith said no. Then left.") == "Dr. Smith said no."
assert F.lead("") == "" and F.lead(None) == "", "no summary, no sentence"
with_summary = piece("Long essay", summary="The essay argues rates stay high. It rests on three charts.", score=8)
without = piece("Plain article", score=7)
_, groups = front([with_summary, without])
book, groups = front([with_summary, without])
arts_by_href = {href: text for _, rows in groups for text, href, *_ in rows}
assert BeautifulSoup(book, "lxml").select_one(f"article{[h for h, t in arts_by_href.items() if t.startswith('The essay')][0]} h1").get_text() == "Long essay", "a summary line links to its article inside the edition"
assert arts_by_href[[h for h, t in arts_by_href.items() if t == "Plain article"][0]] == "Plain article", "a missing summary falls back to the headline"
assert "It rests on three charts" not in book[book.index('id="today"'):book.index('id="s0"')], "only the first sentence"

# ------------------------------------------------------------------ a headline: the headline and its clause, linked to the source
headline_only = line("Brazil votes in a tight runoff", why="Moves emerging-market currencies this week", score=8)
_, groups = front(lists(headline_only))
(label, [(text, href, small, clause)]), = groups
assert (label, text, href, small, clause) == ("World", "Brazil votes in a tight runoff", "https://wire.example/Brazil-votes-in-a-tight-runoff", "Wire", "Moves emerging-market currencies this week."), groups
book, _ = front(lists(headline_only))
assert "Brazil votes in a tight runoff</a>. <span class='fwhy'>Moves emerging-market currencies this week.</span>" in book, "headline, a full stop, then the clause as its own sentence"
_, groups = front(lists(line("Oil climbs again", score=8)))
assert groups[0][1][0][3] == "" and "Oil climbs again</a> <span class='fsrc'>" in front(lists(line("Oil climbs again", score=8)))[0], "no clause: the bare headline"
article = piece("Mercuria in court", section="Markets & Macro", score=8, url="https://www.ft.com/content/eedb7159-65df-45de-91f9-fde8de99e61c")
same_story = line("Mercuria in court", theme="Markets & Macro", score=9, why="Should never show twice.", url=article["url"], to=article)
_, groups = front([article, *lists(same_story)])
assert [t for _, rows in groups for t, *_ in rows] == ["Mercuria in court"] and groups[0][1][0][1].startswith("#a"), "a headline whose story is a full article of the edition shows once, as the article"

# ------------------------------------------------------------------ order: World, Business, Biotech & Health, AI, whatever the ranking
mixed = [piece("AI article", "AI", 9), piece("Deals article", "Deals & Investing", 6), piece("Biotech article", "Biotech & Health", 7), piece("Markets article", "Markets & Macro", 8), piece("World article", "World", 5)]
_, groups = front(mixed)
assert [g for g, _ in groups] == ["World", "Business", "Biotech & Health", "AI"], groups
assert [t for t, *_ in groups[1][1]] == ["Markets article", "Deals article"], "Business holds Markets & Macro and Deals & Investing, the better-ranked first"
_, groups = front([piece("Low", "World", 2), piece("High", "World", 9), piece("Mid", "World", 5, summary="Mid summary says it. More.")] + lists(line("Top headline", score=9.5), line("Tie headline", score=5)))
assert [t for t, *_ in groups[0][1]] == ["Top headline", "High", "Mid summary says it.", "Tie headline", "Low"], "by the editor's score, a full article before a headline on a tie"

# ------------------------------------------------------------------ the cap: ten lines, the Must reads always among them
pool = [piece(f"Article {n:02d}", ["World", "Markets & Macro", "AI"][n % 3], score=n % 10) for n in range(12)] + lists(*[line(f"Headline {n:02d}", ["World", "Biotech & Health"][n % 2], score=3 + n % 6, source=f"Wire {n}") for n in range(12)])
book, groups = front(pool)
shown = [r for _, rows in groups for r in rows]
assert len(shown) == F.LIMIT == 10 and book.count("class='fitem'") == 10, "at most ten lines in all"
best = sorted((c for c in F.candidates(pool)), key=lambda c: (-c["score"], c["kind"] != "article", c["n"]))[:10]
assert {c["text"] for c in best} == {t for t, *_ in shown}, "with no Must read the page is the ten best by the editor's score"
low_must = piece("Quiet but vital", "World", score=0.5, must=True)
low_must2 = piece("Second quiet one", "AI", score=1, must=True)
book, groups = front(pool + [low_must, low_must2])
shown = [r for _, rows in groups for r in rows]
assert len(shown) == 10 and {"Quiet but vital", "Second quiet one"} <= {t for t, *_ in shown}, "a Must read is on the page whatever its score"
assert sorted(r[2] for r in shown if "Must read" in r[2]) == ["Paper Q · Must read", "Paper S · Must read"] and sum("Must read" in r[2] for r in shown) == 2, "only the Must reads are marked, with the plain words"
assert "badge" not in book[book.index('id="today"'):book.index('id="s0"')] and "background" not in (JOB / "template.html").read_text().split(".fgrp{", 1)[1].split("\n.end{", 1)[0], "no badge, no fill"
three = [piece(f"Must {n}", "Long reads", 4, must=True) for n in range(3)] + [piece("World one", "World", 9)]
_, groups = front(three)
assert [g for g, _ in groups] == ["World", "Long reads"] and len(groups[1][1]) == 3, "a Must read from another section follows the themes under that section's name"
_, groups = front([piece("A long read", "Long reads", 9)])
assert groups == [], "a long read that is not a Must read stays off the page"
assert front([piece("One", "World", 5, brief=True), piece("Two", "World", 5, unit=("post", "posts")), piece("Three", "GitHub Trending", 9)])[1] == [], "briefs, lists and the list sections are never lines"
twins = [piece("Same story", "World", 8), *lists(line("Same story", score=9))]
assert sum(len(rows) for _, rows in front(twins)[1]) == 1, "a story once"
assert front([])[1] == [] and "The day in two minutes" not in front([piece("Only", "GitHub Trending")])[0].split('id="toc"')[1], "nothing to show: no front page"

# ------------------------------------------------------------------ nothing invented: every line is a headline, a summary's first sentence, or the ranking run's own clause
summary = "The firm cut its outlook. Sales fell 4% in the quarter."
fed = piece("Fed holds", "Markets & Macro", 9, summary=summary)
book, groups = front([fed, piece("Other piece", "AI", 4)] + lists(line("Chip demand stays strong", "AI", 8, why="Supports AI spending plans")))
texts = [t for _, rows in groups for t, *_ in rows]
assert set(texts) <= {F.lead(summary), "Other piece", "Chip demand stays strong"}, texts
assert "Supports AI spending plans." in book and "Sales fell" not in book[book.index('id="today"'):book.index('id="s0"')]
long_piece = piece("An essay", "Long reads", 9, words=3000, pub="", author_raw="", html="<p>" + "The firm raised money. " * 600 + "</p>")
real_ask, real_which, real_model = briefing.ask_model, briefing.shutil.which, briefing.EDITOR_MODEL
try:
    briefing.shutil.which = lambda name: "/usr/bin/" + name; briefing.EDITOR_MODEL = "haiku"
    prompts = []
    briefing.ask_model = lambda prompt: prompts.append(prompt) or {"0": "The essay covers a firm that raised money. It repeats that point."}
    kept = briefing.add_summaries([dict(long_piece)])[0]
    assert kept["summary"] == "The essay covers a firm that raised money. It repeats that point." and kept["summary"] in BeautifulSoup(kept["html"], "lxml").get_text(), "the front page's text is the summary the piece shows"
    assert "front page" in prompts[0], "the summary run is told its first sentence stands alone"
    briefing.ask_model = lambda prompt: {"0": "It raised $9 billion. Nothing else."}
    assert "summary" not in briefing.add_summaries([dict(long_piece)])[0], "a rejected summary leaves nothing for the front page"
finally: briefing.ask_model, briefing.shutil.which, briefing.EDITOR_MODEL = real_ask, real_which, real_model
assert '"front"' not in briefing.EDITOR_PROMPT and "front" not in briefing.apply_edit([piece("A")], {"front": [{"id": 0, "line": "x", "why": "y"}]})[0], "the editor is no longer asked to write front-page lines"

# ------------------------------------------------------------------ the same lines in the PDF's page and in the EPUB
rows = [piece("Long essay", "Markets & Macro", 8, summary="The essay argues rates stay high. It rests on three charts.", must=True), piece("World piece", "World", 6)] + lists(headline_only, line("Oil climbs again", "Markets & Macro", 7, source="Semafor"))
_, _, book = briefing.render([a for a in rows if not a.get("lines")], [], now, "Morning", heads=[a for a in rows if a.get("lines")])
html_lines = [(el.get_text(" ", strip=True)) for el in BeautifulSoup(book, "lxml").select("section.today .fgrp, section.today p.fitem")]
assert html_lines[0] == "World" and html_lines[-1].endswith("Semafor") and "Must read" in " ".join(html_lines)
print_page = (JOB / "print.html").read_text().replace("%%BOOK%%", book)
groups_n = book.count('class="fgrp"')
assert print_page.count("class='fitem'") == len(html_lines) - groups_n == 4 and groups_n == 2 and ".fgrp" in print_page and ".fwhy" in print_page, "the PDF is made from the same markup, styled in print.html"
b = BeautifulSoup(book, "lxml"); briefing.kindle_structure(b); briefing.kindle_markup(b)
epub = b.get_text(" ", strip=True); today = epub[epub.index("The day in two minutes"):epub.index("Contents")]
for needle in ("World", "Business", "Brazil votes in a tight runoff. Moves emerging-market currencies this week. Read ›", "The essay argues rates stay high. Read ›", "Paper L · Must read", "Oil climbs again Read ›"):
    assert needle in today, (needle, today[:600])
assert not b.select(".fitem") and not b.select(".fgrp") and len(b.select("div.item")) >= 4, "Kindle gets plain blocks"

assert F.candidates([piece("Bloomberg Morning Briefing", "Markets & Macro", 9, daily=True)]) == [], "a daily newsletter is never a front-page article: its stories come as headlines"
print("briefing front page checks passed")
