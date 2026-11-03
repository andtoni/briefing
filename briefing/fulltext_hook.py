"""Plug-in point for full-length articles from sources the reader subscribes to. In this public copy it returns nothing.

The private version of the Briefing has a module here that reads a few paywalled publications in full through the operator's own signed-in
browser sessions. That module is not published: it depends on one person's subscriptions and sessions, and on infrastructure outside this
repository. What remains is the contract the rest of the Briefing relies on, so the edition builds the same way without it.

To add your own source, replace `fetch` with a function that returns a `Result` whose `entries` are shaped like miniflux.entry() output
(id, feed_id, title, author, content, url, published, _source, _section) plus `_fulltext` set to a stable story key. The rest of the Briefing
then treats each one as a full article: it is never a briefing or a long read, and its section comes from `_section`.
"""
import dataclasses

@dataclasses.dataclass
class Result:
    entries: list      # full-length articles, in the miniflux.entry() shape plus `_fulltext`
    notices: list      # one plain line per source that could not be read, shown in the edition
    ids: list          # story keys to remember, so they are not offered again
    status: dict       # per source: what happened, for the run log
    catalog: list = dataclasses.field(default_factory=list)      # every feed item seen, {title, url}: lets a headline find its article

def fetch(since,entries,state,*,curl=None,ask=None,profile='',now=None,local_now=None,edition='Morning'):
    """No full-text source is configured: nothing to add, nothing to report."""
    return Result([],[],[],{})

def remember(state,ids):
    """Nothing to remember: `fetch` never returns a story."""
    return None
