"""The edition's front page, "The day in two minutes": at most ten lines, picked from the full articles and the headline lists by the editor's ranking.

A full article in the edition is a line made of its In short summary's first sentence (its headline when it has no summary) and links to the article inside the edition.
A headline-only story is a line made of the headline and a short "why it matters" clause from the headline ranking run, and links to the source. The Must read pieces are always on the
page, marked with the plain words "Must read". Lines are grouped World, Business (Markets & Macro, Deals & Investing), Biotech & Health, AI, and a Must read that sits in another
section follows them under that section's name. Nothing here is written by a model for the page: a line is a headline or a generated summary's own first sentence.
"""
import html
import headlines as H
import rules as R

LIMIT = 10
BUSINESS = ('Markets & Macro', 'Deals & Investing')
GROUPS = ('World', 'Business', 'Biotech & Health', 'AI')

def group_of(section): return 'Business' if section in BUSINESS else section

def lead(summary):
    """The first sentence of a generated summary, unchanged ('' when there is none)."""
    t = H.tidy(summary)
    return H.SENTENCE.split(t, 1)[0] if t else ''

def stop(t): return t if t[-1:] in '.!?' else t + '.'

def candidates(arts):
    """Everything the page may show, in the edition's order: the plain full articles of a theme (or any Must read) and the headlines that are not also an article of the edition."""
    out = []
    for n, a in enumerate(arts):
        if a.get('lines'):
            for x in a['lines']:
                if x.get('to') is None and x.get('url') and x.get('title'):
                    out.append(dict(kind='headline', group=group_of(x.get('theme') or a['section']), score=x.get('score', 0), text=x['title'], why=x.get('why') or '',
                                    source=x['source'], url=x['url'], must=False, key=H.norm(x['title']), n=n))
        elif not (a.get('brief') or a.get('unit') or a.get('gap') or a.get('daily')) and (a['section'] in R.THEMES or a.get('must')):      # a daily newsletter's stories reach the page as headlines
            out.append(dict(kind='article', group=group_of(a['section']), score=a.get('score', 0), text=lead(a.get('summary')) or a['title'], why='',
                            source=a['source'], piece=a, must=bool(a.get('must')), key=H.norm(a['title']), n=n))
    return out

def pick(arts, limit=LIMIT):
    """The page as [(group, [line])]: the Must reads first, then the best of the rest by the editor's score (a full article before a headline on a tie), at most `limit` lines in all,
    a story once. Groups follow GROUPS, then any other section in edition order; inside a group the better-ranked line comes first."""
    chosen, seen = [], set()
    for c in sorted(candidates(arts), key=lambda c: (not c['must'], -c['score'], c['kind'] != 'article', c['n'])):
        if len(chosen) >= limit: break
        if c['key'] in seen: continue
        seen.add(c['key']); chosen.append(c)
    groups = {}
    for c in sorted(chosen, key=lambda c: (-c['score'], c['kind'] != 'article', c['n'])): groups.setdefault(c['group'], []).append(c)
    return sorted(groups.items(), key=lambda g: (GROUPS.index(g[0]), 0) if g[0] in GROUPS else (len(GROUPS), min(c['n'] for c in g[1])))

def page_html(groups, local):
    """The lines as markup: a plain group label, then one paragraph per line. An article line links to the piece in the edition (`local(piece)` gives its anchor id), a headline line to its source.
    The why clause follows the headline as its own sentence; the publication (in italics) and the words Must read close the line in small grey type."""
    esc = html.escape; out = ''
    for label, lines in groups:
        out += f'<div class="fgrp">{esc(label)}</div>'
        for c in lines:
            if c['kind'] == 'article':
                go = local(c['piece']); link = f"<a href='#{go}' data-go='{go}'>{esc(c['text'])}</a>"
            else: link = f"<a href='{esc(c['url'])}' target='_blank' rel='noopener'>{esc(c['text'])}</a>" + ('.' if c['why'] and c['text'][-1:] not in '.!?' else '')
            why = f" <span class='fwhy'>{esc(stop(c['why']))}</span>" if c['why'] else ''
            out += f"<p class='fitem'>{link}{why} <span class='fsrc'><b>{esc(c['source'])}</b>{' · Must read' if c['must'] else ''}</span></p>"
    return out
