"""The Briefing's reader: every web feed and newsletter, read from a Miniflux feed reader.

Newsletters reach Miniflux as feeds too (an email-to-feed bridge turns each sender's mail into one Atom feed), so one reader carries both.
Miniflux is only read: GET /v1/entries with an API token, nothing is marked read, starred or changed. Each entry is returned in the shape the
Briefing builds pieces from, so it goes through the same cleaning, rules, de-duplication, summaries and Kindle output.

Left out: the categories in EXCLUDED_CATEGORIES, the feeds in EXCLUDED_FEEDS, and a feed's back catalogue.
"""
import datetime,json,time,urllib.error,urllib.parse,urllib.request

TIMEOUT=30
PAGE=100
MAX_PAGES=30
ID_BASE=10**11                                  # keeps an entry id clear of the small ids the Briefing gives its own pieces
BACKLOG_DAYS=2                                  # a feed added today delivers its whole back catalogue as new; keep what was published around the window
PER_FEED=25                                     # newest entries per feed in one edition
LATE_HOURS=12                                   # an entry published this long before the window and stored in it is a feed's back catalogue, not a late arrival
BURST=6                                         # this many entries of one feed dated to the same second are a back catalogue dated on arrival (a feed with no dates)
UNCATEGORISED={'all','uncategorized',''}        # Miniflux's default category
EXCLUDED_CATEGORIES={'jobs'}                    # categories that are not news (matched case-insensitively)
EXCLUDED_FEEDS=('/test.xml',)                   # feed addresses (by ending) never read, e.g. a bridge's test address that receives only sign-in codes

def utc(stamp):
    """An ISO 8601 stamp with any offset as UTC, or None."""
    try: when=datetime.datetime.fromisoformat((stamp or '').replace('Z','+00:00'))
    except ValueError: return None
    return when.astimezone(datetime.timezone.utc) if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)

def stamp(when): return when.strftime('%Y-%m-%dT%H:%M:%S.000000Z')

def excluded(raw):
    feed=raw.get('feed') or {}
    category=((feed.get('category') or {}).get('title') or '').strip().lower()
    return category in EXCLUDED_CATEGORIES or (feed.get('feed_url') or '').endswith(EXCLUDED_FEEDS)

def entry(raw):
    """The entry shape the Briefing builds pieces from, or None when the entry has no usable date or comes from an excluded feed."""
    if excluded(raw): return None
    published=utc(raw.get('published_at')) or utc(raw.get('created_at'))
    if published is None: return None
    feed=raw.get('feed') or {}
    category=((feed.get('category') or {}).get('title') or '').strip()
    return dict(id=ID_BASE+int(raw['id']),feed_id=raw.get('feed_id') or feed.get('id'),title=(raw.get('title') or '').strip(),author=(raw.get('author') or '').strip(),
        content=raw.get('content') or '',url=raw.get('url') or '',published=stamp(published),created_at=stamp(utc(raw.get('created_at')) or published),
        _source=(feed.get('title') or 'Unknown').strip(),_section='Other' if category.lower() in UNCATEGORISED else category)

def cap(rows):
    """Per feed: drop a back catalogue dated on arrival (BURST or more entries on one published second), then keep the newest PER_FEED. Order is kept."""
    feeds={}
    for x in rows: feeds.setdefault(x['_source'] if x['feed_id'] is None else x['feed_id'],[]).append(x)
    keep=set()
    for group in feeds.values():
        seconds={}
        for x in group: seconds[x['published'][:19]]=seconds.get(x['published'][:19],0)+1
        dated=[x for x in group if seconds[x['published'][:19]]<BURST]
        keep|={id(x) for x in sorted(dated,key=lambda x:(x['published'],x['id']))[-PER_FEED:]}
    return [x for x in rows if id(x) in keep]

class Unavailable(Exception): pass

def api(base,token,path,opener=urllib.request.urlopen):
    """GET /v1/<path> as JSON; tried three times on a network error or a 5xx, never on anything else."""
    req=urllib.request.Request(base.rstrip('/')+'/v1/'+path,headers={'X-Auth-Token':token,'Accept':'application/json'})
    for pause in (2,8,None):
        try:
            with opener(req,timeout=TIMEOUT) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (401,403): raise Unavailable('refused the API token, so it may need replacing') from e
            if e.code<500: raise Unavailable(f'answered HTTP {e.code}') from e
            failure=Unavailable(f'answered HTTP {e.code}')
        except (urllib.error.URLError,OSError,json.JSONDecodeError) as e: failure=Unavailable('could not be reached')
        if pause is None: raise failure
        time.sleep(pause)

def entries(base,token,floor,get=api):
    """Every read and unread entry published since `floor`, oldest first, excluded feeds left out."""
    out=[]
    for page in range(MAX_PAGES):
        query=urllib.parse.urlencode([('status','unread'),('status','read'),('published_after',int(floor.timestamp())),('order','published_at'),('direction','asc'),('limit',PAGE),('offset',page*PAGE)])
        batch=get(base,token,'entries?'+query)
        rows=(batch or {}).get('entries') or []
        out+=[e for e in (entry(r) for r in rows) if e]
        if len(rows)<PAGE: return out
    raise Unavailable(f'returned more than {MAX_PAGES*PAGE} entries in the window, more than one run reads')

def fetch(since,env,get=api):
    """(the entries Miniflux stored since `since`, capped per feed; notice). An unset address or token, or an unreachable Miniflux, returns nothing and the notice."""
    token=(env.get('BRIEFING_MINIFLUX_TOKEN') or '').strip()
    if not token: return [],'Feeds unavailable: the Miniflux API token is not set.'
    base=(env.get('BRIEFING_MINIFLUX_URL') or '').strip()
    if not base: return [],'Feeds unavailable: the Miniflux address (BRIEFING_MINIFLUX_URL) is not set.'
    try: wide=entries(base,token,since-datetime.timedelta(days=BACKLOG_DAYS),get)
    except Unavailable as e: return [],f'Feeds unavailable: Miniflux {e}.'
    start=stamp(since)[:19]; oldest=stamp(since-datetime.timedelta(hours=LATE_HOURS))[:19]
    return cap([x for x in wide if x['created_at'][:19]>=start and x['published'][:19]>=oldest]),''
