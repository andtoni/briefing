"""Per-publication rules, the edition's themes, and what counts as a long read.

The Briefing groups its stories under five themes (THEMES); a Miniflux category, a publication and the words of a story say which (theme_of, classify).
A publication that mails both written newsletters and link roundups gets one entry in PUBLICATIONS: the series that are lists of headlines. A list's items
become headlines in the theme sections (headlines.py), never a whole piece. Every other series is a written newsletter and is a piece. A publication with no
entry is never filtered, and cross-publication overlap never removes a piece: it can only remove one repeated headline line.
Separately, headline_list finds any newsletter, of any publication, whose body is mostly a run of short headline blocks (a headline, a one-line summary and
a byline) with little prose around them; its items become headlines too.
A long single-author piece (long_read) is one that is long enough to need a summary at the top and is not a roundup: a series in PUBLICATIONS' list, a publication or
title that is a briefing by nature (ROUNDUP), or a run of short stories under many headings. Those pieces make up the Long reads section.
"""
import re
from bs4 import BeautifulSoup

THEMES = ('World', 'Markets & Macro', 'Deals & Investing', 'Biotech & Health', 'AI')
LONG_READS = 'Long reads'
# What a Miniflux category says about the theme; Business is split by the words of the story.
SECTION_THEME = {'World': 'World', 'Business': 'Business', 'Biopharma': 'Biotech & Health', 'Medicine & Science': 'Biotech & Health', 'Health AI': 'Biotech & Health',
                 'Health Policy': 'Biotech & Health', 'Medtech': 'Biotech & Health', 'AI & Engineering': 'AI'}

PUBLICATIONS = {
    'STAT': dict(
        match=re.compile(r'\bSTAT\b'),
        lists={'daily recap', 'stat today', 'morning rounds', 'cancer briefing', 'pharmalot', 'weekend reads', 'pharmalittle'},
    ),
}
LONG_WORDS=1200    # a piece this long gets a summary at the top
MULTI_BLOCKS=6     # six or more headings ...
MULTI_MEAN=250     # ... averaging at most this many words each are several stories, not one essay
# Publications and series that are briefings or link roundups whatever their length, matched against "source author title".
ROUNDUP=re.compile(r"semafor|the economist|axios|firstft|\(briefing\)|endpoints|\b(daily|morning|evening|afternoon|ft) briefing|\bround-?up\b|what.s news|morning brief|evening brief|market wrap|markets? [ap]\.m\.|10-point|longreads|open thread|charts of the week|weekly (digest|news|links)|\bin brief\b",re.I)
# Promotional digests whose author field carries no series name, recognised by how their body opens.
MUTED_OPENINGS = [
    # 'The Economist This Week' (Saturday edition): a picture-and-link promo for the weekly issue, about 25 images and 46 links around 350 words.
    ('The Economist', re.compile(r'The Economist This Week')),
]
OPENING_CHARS=400
# STAT mails every email type to its inbox; the Brief keeps its newsletters and STAT+ articles and drops its alerts, promotions and events, by the author field or the subject.
STAT_DROP_AUTHOR=re.compile(r"\balerts?\b|breaking news|\bevents\b|webinars?|marketing|promotions?|\bsponsored\b|\bmembership\b|\bsubscriptions?\b",re.I)
STAT_DROP_TITLE=re.compile(r"webinar|join us\b|livestream|% off|\bdiscount\b|last chance|verify your email|\bregister (now|today|for)\b|save the date|\btickets?\b|\binvitation\b|"
                           r"subscribe (now|today)|special offer",re.I)      # promotional subjects only: "adverse events" or "raises its offer" is journalism
# Daily newsletters: the headline-summary mailings (roundups, briefings, the dailies of Semafor, The Economist, Bloomberg, the WSJ, the FT, Axios and STAT), matched on
# "source author title". A section prints its stack (SECTIONS, PRINTED) whole; any other daily newsletter is one line in the section's Also today.
DAILY=re.compile(r"semafor|\bin brief\b|the economist|what.s news|firstft|\(briefing\)|\bft briefing|\bbriefing\b|commodities note|markets? [ap]\.m\.|10-point|five things|"
                 r"markets daily|economics daily|ai today|tech daily|balance of power|morning rounds|the readout|medtech dive|unhedged|daily recap|stat\+? today|pharmalot|pharmalittle|"
                 r"cancer briefing|axios|endpoints \| main edition|daily ping",re.I)
# Each theme's daily newsletters, in order: the anchor, printed whole at the top, then the newsletters listed after it (each matched on "source author title" and the
# opening of the mailing). When the anchor did not arrive, the section's next listed newsletter that did takes its place and the build log says so. A daily newsletter
# named here is filed in that section. Bloomberg's Morning and Evening Briefings carry no series name, only the day's headline: who() marks them "bloomberg briefing".
SECTIONS = (
    ('World', ("The Economist, The World in Brief", r"world in brief"),
     (("The Economist, The US in Brief", r"us in brief"), ("Semafor Flagship", r"semafor flagship"), ("FT FirstFT", r"firstft"), ("WSJ What's News", r"what.s news"))),
    ('Markets & Macro', ("Bloomberg Morning or Evening Briefing", r"bloomberg briefing|bloomberg.*morning briefing|morning briefing.*bloomberg"),
     (("WSJ Markets A.M./P.M.", r"markets? [ap]\.m\."), ("FT Unhedged", r"unhedged"), ("FT markets briefing", r"markets (morning|afternoon|evening) briefing|commodities note"),
      ("The Economist, Business in Brief", r"business in brief"))),
    ('Deals & Investing', ("Axios Pro Rata", r"pro rata"),
     (("FT deals newsletter", r"due diligence"), ("Bloomberg Deals", r"bloomberg deals"))),
    ('Biotech & Health', ("STAT Morning Rounds", r"morning rounds"),
     (("STAT The Readout", r"the readout"), ("MedTech Dive", r"medtech dive"), ("Semafor Health", r"semafor.*health"), ("Endpoints", r"endpoints"), ("Nature Briefing", r"nature briefing"))),
    ('AI', ("Bloomberg AI Today", r"ai today"),
     (("Semafor Technology", r"semafor.*tech"), ("FT tech and AI newsletters", r"#?techft|the ai shift"))),
)
# The rest of each section's stack, printed whole after its anchor (Andrea, 28 Oct 2026): every other daily newsletter goes to Also today, and nothing printed is cut.
PRINTED = {
    'World': r"us in brief|semafor flagship",
    'Markets & Macro': r"markets? [ap]\.m\.|unhedged",
    'Biotech & Health': r"the readout|medtech dive",
    'AI': r"semafor.*tech",
}
ANCHORS = tuple((sec,name,pat) for sec,(name,pat),_ in SECTIONS)
# Other daily newsletters whose name says where they belong; any other is filed by its Miniflux category and words, like a piece.
DAILY_SECTION = (
    ('World', r"the us in brief"),
    ('Markets & Macro', r"five things|markets daily|economics daily|10-point"),
    ('Biotech & Health', r"health care inc|pharmalittle|pharmalot|daily recap|stat\+? today|cancer briefing"),
    ('AI', r"daily ping"),
)
# Admin and promotional mailings, never shown: sign-up, verification, welcome, confirmation, opt-in, email-change, promotion, webinar, fellowship and event mails.
ADMIN_TITLE=re.compile(r"\b(confirm|verify) your\b|\bverification code\b|\bconfirmation required\b|\bplease (confirm|verify)\b|opt-in request|subscription confirmed|^action required\b|"
                       r"\be-?mail (address )?(change|has been changed)|\bchang(e|ing) your e-?mail|update your e-?mail|e-?mail address has been changed|\bwebinars?\b|"
                       r"\bannouncing the .*fellowship|^events?:|^integration complete!?$|the takes are coming|\bregister (now|today)\b|save the date|\bjoin us\b|"
                       r"\byour (payment )?receipt\b|^receipt (for|from)\b|^sign up now\b",re.I)      # phrase shapes of admin mail, so "Senate confirms nominee" stays
WELCOME=re.compile(r"^welcome\b",re.I)      # a welcome mail: the subject opens with Welcome and the mail talks about the subscription
WELCOME_BODY=re.compile(r"subscri|newsletter|inbox|signed up|sign up|thanks for joining|thank you for joining|you.re in\b",re.I)
ADMIN_AUTHOR=re.compile(r"\bevents?\b|webinars?|^substack$|catchall",re.I)
SAME_STORY=.6      # two pieces of one source whose titles share this share of their words are one story
MIN_WORDS=4        # shorter headings are section labels, not headlines
LIST_MIN_BLOCKS=5  # a headline list has at least this many h2 headline blocks
LIST_MAX_MEAN=30   # ... that average at most this many words each (headline, one-line summary, byline)
LIST_MIN_SHARE=.5  # ... and make up at least this share of the piece, so a written intro or essay keeps it

def norm(t): return re.sub(r'\W+',' ',(t or '').lower()).strip()

def publication(source, author):
    """The PUBLICATIONS key an entry belongs to, or ''."""
    for name,rule in PUBLICATIONS.items():
        if rule['match'].search(f'{source} {author}'): return name
    return ''

def series(author):
    """The newsletter name a mailing carries after the bar in its author field ('STAT | Daily Recap'), or ''."""
    return norm(author.split('|',1)[1]) if '|' in (author or '') else ''

def muted(entry):
    """True for a promotional digest named in MUTED_OPENINGS: it holds no story, only a picture-and-link advertisement for an issue."""
    who=f"{entry['_source']} {entry.get('author') or ''}"
    opening=BeautifulSoup(entry.get('content') or '','html.parser').get_text(' ')[:OPENING_CHARS]
    return any(name in who and pattern.search(opening) for name,pattern in MUTED_OPENINGS)

def stat_noise(entry):
    """True for a STAT alert, promotional or event email: the Brief keeps only STAT's newsletters and STAT+ articles."""
    if publication(entry.get('_source',''),entry.get('author') or '')!='STAT': return False
    return bool(STAT_DROP_AUTHOR.search(entry.get('author') or '') or STAT_DROP_TITLE.search(entry.get('title') or ''))

def admin(entry):
    """True for an admin or promotional mailing (ADMIN_TITLE, ADMIN_AUTHOR): it never reaches the edition."""
    title=entry.get('title') or ''
    welcome=bool(WELCOME.search(title)) and bool(WELCOME_BODY.search(BeautifulSoup(entry.get('content') or '','html.parser').get_text(' ')[:OPENING_CHARS*2]))
    return welcome or bool(ADMIN_TITLE.search(title) or ADMIN_AUTHOR.search((entry.get('author') or '').strip()))

# Newsletter names (Andrea, 30 Oct 2026): a named newsletter shows its name in the byline, "<b>Publisher</b> · Newsletter · Type · Author", and the name leaves the title.
# A name arrives as a title prefix ("Money Stuff: ...") or in the sender ("Semafor Flagship", "STAT | Morning Rounds", "Brainfood by Simon Taylor"); Bloomberg's briefings carry
# none and are named by the hour they arrive.
TITLE_SERIES=re.compile(r"^(Money Stuff|Axios Pro Rata|AI Today|Economics Daily|Going Private|Markets [AP]\.M\.|The 10-Point|Simply Science|Money Talks|The War Room|"
                        r"Checks and Balance|The Bottom Line|Unhedged|FirstFT|Commodities Note|Markets (?:morning|afternoon|evening) briefing)\s*:\s*(.+)$",re.I)
def bare(title):
    """A title without a newsletter's name in front ("FirstFT: Netanyahu leads" -> "Netanyahu leads"), for comparing titles across editions: label() takes the name out."""
    m=TITLE_SERIES.match(title or '')
    return m.group(2).strip() if m else (title or '')
SERIES_NOT=('news','opinion','briefing','newsletters')      # what follows a publisher in a sender without naming a newsletter
SERIES_NAMES={'axios pro rata':'Pro Rata','firstft americas':'FirstFT','today':'Economist Today'}
SENDER_PREFIXES=('The Economist','Bloomberg','Semafor','WSJ','FT','STAT+','STAT','Endpoints','a16z','Nature Briefing')
PERSON=re.compile(r"^[A-Z][\w.'’-]*(?: [A-Z][\w.'’-]*){1,3}$")
def sender_series(sender,publisher):
    """(newsletter name, person) from a sender name: "STAT | Morning Rounds" -> ('Morning Rounds',''), "Mario | Health Tech" -> ('Health Tech','Mario'),
    "Semafor Flagship" -> ('Flagship',''), "Brainfood by Simon Taylor" -> ('Brainfood','Simon Taylor'), "Matt Levine at Bloomberg Opinion" -> ('','Matt Levine')."""
    s=' '.join((sender or '').split())
    if not s: return '',''
    if '|' in s:
        left,right=(x.strip() for x in s.split('|',1))
        if norm(right) in (norm(publisher),'stat'): return '',left
        return SERIES_NAMES.get(norm(right),right),('' if norm(left) in ('stat','endpoints') or norm(left)==norm(publisher) else left)
    m=re.match(r"^(.+?) (at|from) (.+)$",s)
    if m and PERSON.match(m.group(1)): return ('' if m.group(2)=='at' else m.group(3)),m.group(1)
    m=re.match(r"^(.+?) by (.+)$",s)
    if m and PERSON.match(m.group(2)): return m.group(1),m.group(2)
    if norm(s) in SERIES_NAMES: return SERIES_NAMES[norm(s)],''
    for p in SENDER_PREFIXES:
        if s.lower().startswith(p.lower()+' ') or s.lower().startswith(p.lower()+':'):
            rest=s[len(p):].strip(' :|·-')
            if rest and norm(rest) not in SERIES_NOT: return SERIES_NAMES.get(norm(rest),rest),''
    return '',''

def bloomberg_briefing(a):
    """True for Bloomberg's Morning or Evening Briefing: a Bloomberg mailing with no series name in its author or title, only the day's headline."""
    return (a.get('source') or a.get('_source',''))=='Bloomberg' and norm(a.get('author_raw') or a.get('author') or '') in ('','bloomberg') and not re.match(r"^[^:]{2,40}:\s",a.get('title') or '')
def who(a): return f"{a.get('source') or a.get('_source','')} {a.get('author_raw') or a.get('author') or ''} {a.get('title','')}"+(' bloomberg briefing' if bloomberg_briefing(a) else '')

def daily(a):
    """True for a daily newsletter (DAILY, a SECTIONS or DAILY_SECTION name, or a Bloomberg newsletter with no series name, which is one of its dailies). An article read in full never is."""
    if a.get('fulltext') or a.get('unit') or a.get('gap'): return False
    if a.get('source')=='Bloomberg' and norm(a.get('author_raw') or '') in ('','bloomberg'): return True
    return bool(DAILY.search(who(a))) or bool(daily_section(a))

def opening(a): return BeautifulSoup(a.get('html') or a.get('content') or '','html.parser').get_text(' ')[:OPENING_CHARS]

def daily_section(a):
    """The section SECTIONS (or DAILY_SECTION) files this newsletter under, or ''."""
    text=f"{who(a)} {opening(a)}"
    for sec,(_,pat),rest in SECTIONS:
        if any(re.search(p,text,re.I) for p in (pat,*(p for _,p in rest))): return sec
    return next((sec for sec,p in DAILY_SECTION if re.search(p,text,re.I)),'')

def is_anchor(a,section):
    """True when this newsletter is the anchor SECTIONS names for `section`."""
    pat=next((p for s,_,p in ANCHORS if s==section),None)
    return bool(pat) and bool(re.search(pat,f"{who(a)} {opening(a)}",re.I))

def printed(a,section):
    """True when this newsletter belongs to the stack `section` prints whole after its anchor (PRINTED)."""
    pat=PRINTED.get(section)
    return bool(pat) and bool(re.search(pat,f"{who(a)} {opening(a)}",re.I))

def daily_rank(a,section):
    """The newsletter's place in its section's SECTIONS order: 0 for the anchor, then 1, 2 ... for the newsletters listed after it, len+1 for any other."""
    text=f"{who(a)} {opening(a)}"
    row=next(((pat,rest) for s,(_,pat),rest in SECTIONS if s==section),None)
    if not row: return 0
    pats=(row[0],*(p for _,p in row[1]))
    return next((n for n,p in enumerate(pats) if re.search(p,text,re.I)),len(pats))

def title_words(t): return set(norm(re.sub(r'\s*\|\s*STAT\+?.*$','',t or '')).split())

def same_story(a,b):
    """True when two pieces of one source tell one story: their titles share at least SAME_STORY of their words (a breaking alert and the article that follows it)."""
    if a.get('source')!=b.get('source'): return False
    x,y=title_words(a.get('title')),title_words(b.get('title'))
    return min(len(x),len(y))>=5 and len(x&y)/len(x|y)>=SAME_STORY

def collapse(arts):
    """One piece per story within a source: of near-duplicate titles the longest piece is kept, in the place of the first."""
    out=[]
    for a in arts:
        twin=next((k for k,b in enumerate(out) if same_story(a,b)),None)
        if twin is None: out.append(a)
        elif a.get('words',0)>out[twin].get('words',0): out[twin]=a
    return out

def headline_series(entry):
    """True for a mailing of a series in PUBLICATIONS that is a list of headlines (STAT's Daily Recap, Pharmalot, Pharmalittle ...)."""
    pub=publication(entry['_source'],entry.get('author') or '')
    return bool(pub) and series(entry.get('author')) in PUBLICATIONS[pub]['lists']

# ------------------------------------------------------------------ themes
_NOT_DEALS=r"(trade|peace|ceasefire|nuclear|budget|climate|tax|debt|plea|truce) deals?"
_WORDS=dict(
    deals=r"\b(acqui\w*|merger|mergers|takeover|buyouts?|lbo|private equity|private credit|venture|funding round|series [a-f]\b|raises? \$|raised \$|ipo|spac|stake in|bid for|divest\w*|spin-?off|"
          r"unicorn|valuation|fundrais\w*|dealmak\w*|hedge funds?|asset manage\w*|m&a|deals?|buys|to buy|sells|consortium|backed by)\b",
    markets=r"\b(stocks?|shares|bonds?|yields?|treasur\w+|inflation|interest rates?|fed|federal reserve|central bank|ecb|boj|gdp|econom\w+|oil|crude|gold|dollar|currenc\w+|tariffs?|recession|"
            r"earnings|equit\w+|markets?|s&p|nasdaq|dow|commodit\w+|payrolls|jobs report|rates?|bank|banks|banking|credit)\b",
    bio=r"\b(drugs?|pharma\w*|biotech\w*|fda|clinical|trials?|vaccines?|cancer|medic\w+|hospitals?|health\w*|patients?|therap\w+|diseases?|biolog\w*|genom\w*|crispr|gene|glp-?1|obesity|"
         r"oncolog\w*|medicaid|medicare|nih|cdc|epidemic|pandemic|doctors?)\b",
    ai=r"\b(ai|artificial intelligence|openai|anthropic|chatgpt|llms?|large language|machine learning|nvidia|chips?|semiconductors?|data cent(?:er|re)s?|gpus?|deepmind|robots?|robotics|software|cloud)\b",
    world=r"\b(war|ceasefire|iran|israel|gaza|ukraine|russia|china|election|elections|president|parliament|minister|military|sanctions?|nato|trump|congress|senate|court|protests?|terror\w*|"
          r"government|summit|diplomat\w*)\b",
)
_PRIORITY=(('bio','Biotech & Health'),('ai','AI'),('deals','Deals & Investing'),('markets','Markets & Macro'),('world','World'))

def classify(text, hint=''):
    """The theme the words of a story point to. With hint 'Business' the answer is Deals & Investing or Markets & Macro (the latter when nothing else says); with no hint it is the
    theme with the most matches, or '' when none matches. A hint that is already a theme is returned as it is."""
    if hint in THEMES: return hint
    text=re.sub(_NOT_DEALS,' ',text or '',flags=re.I)
    n={k:len(re.findall(p,text,re.I)) for k,p in _WORDS.items()}
    if hint=='Business': return 'Deals & Investing' if n['deals']>n['markets'] else 'Markets & Macro'
    best=max(n.values())
    return next((name for key,name in _PRIORITY if n[key]==best),'') if best else ''

def theme_of(section, source='', author='', text=''):
    """The section a piece is filed under: STAT is Biotech & Health; a Miniflux category maps to a theme; Business is split by its words; Life, Saved and Other stay as they are
    (Other is filed by its words when they point anywhere)."""
    if publication(source,author): return 'Biotech & Health'
    mapped=SECTION_THEME.get(section)
    if mapped == 'Business': return classify(text,'Business')
    if mapped: return mapped
    return classify(text) or section if section=='Other' else section

def headline_keys(h, by_text):
    """What identifies a headline line: its link without the query and, for a publication in PUBLICATIONS,
    its text without the STAT+ prefix. Any other piece matches on a link only, so a recurring section
    heading such as "What we're reading" never counts as a repeat."""
    a=h.find('a'); url=re.sub(r'[?#].*','',a.get('href','')) if a else ''
    text=norm(re.sub(r'^\s*STAT\+?\s*\|\s*','',h.get_text(' ',strip=True).rstrip('↑ ')))
    return ({text} if by_text and len(text.split())>=MIN_WORDS else set())|({url} if url.startswith('http') else set())

def line_blocks(body):
    """Each h2 headline of a cleaned piece with the paragraphs under it up to the next heading."""
    out=[]
    for h in body.find_all('h2'):
        block=[h]
        for s in h.next_siblings:
            if getattr(s,'name',None) in ('h2','hr'): break
            block.append(s)
        out.append(block)
    return out

def dedupe(arts):
    """Drop a headline line already shown in an earlier piece, in place. A piece keeps at least its fresh lines and stays whole when every line repeats.
    Returns the kept pieces."""
    shown=set()
    for a in arts:
        body=BeautifulSoup(f"<body>{a['html']}</body>",'lxml').body
        blocks=line_blocks(body); keys=[headline_keys(b[0],bool(PUBLICATIONS.get(a.get('pub')))) for b in blocks]
        repeat=[bool(k&shown) for k in keys]
        if any(repeat) and len(blocks)>sum(repeat):
            for b,r in zip(blocks,repeat):
                if r:
                    for el in b: el.extract()
            a['html']=''.join(str(c) for c in body.find_all(recursive=False))
        for k in keys: shown|=k
    return arts

def headline_list(html):
    """A reason string when most of a cleaned piece is a run of short headline blocks, else ''. Measured on the week of
    7 to 24 October: the STAT lists (Pharmalot, Daily Recap, Weekend Reads) average 18 to 21 words a block and fill 65 to 95%
    of the piece; written newsletters average 46 words or more a block, and a list with a long written intro (STAT's
    First Opinion letter) fills 40%."""
    body=BeautifulSoup(f"<body>{html}</body>",'lxml').body
    blocks=line_blocks(body)
    if len(blocks)<LIST_MIN_BLOCKS: return ''
    n=[sum(len(getattr(e,'get_text',lambda *a,**k:str(e))(' ',strip=True).split()) for e in b) for b in blocks]
    total=len(body.get_text(' ',strip=True).split()); mean=sum(n)/len(n)
    if mean<=LIST_MAX_MEAN and sum(n)>=LIST_MIN_SHARE*total:
        return f'{len(n)} headline blocks averaging {mean:.0f} words fill {100*sum(n)//max(1,total)}% of the piece'
    return ''

def multi_story(html):
    """True for a piece that is several short stories under many headings (Decoding Bio's BioByte), not one essay with a few sections."""
    body=BeautifulSoup(f"<body>{html}</body>",'lxml').body
    blocks=line_blocks(body)
    if len(blocks)<MULTI_BLOCKS: return False
    n=[sum(len(getattr(e,'get_text',lambda *a,**k:str(e))(' ',strip=True).split()) for e in b) for b in blocks]
    return sum(n)/len(n)<=MULTI_MEAN

def long_read(a):
    """True for a long single-author piece: at least LONG_WORDS words, not a brief feed or a notice, not a roundup by the per-publication rules,
    by name (ROUNDUP) or by structure (multi_story)."""
    if a.get('brief') or a.get('unit') or a.get('gap') or a['words']<LONG_WORDS: return False
    rule=PUBLICATIONS.get(a.get('pub'))
    if rule and series(a.get('author_raw')) in rule['lists']: return False
    if not a.get('fulltext') and ROUNDUP.search(f"{a['source']} {a.get('author_raw') or ''} {a['title']}"): return False      # an article read in full is never a briefing, whatever its publication is called
    return not multi_story(a['html'])


ESSAY_WORDS=400    # a newsletter or blog piece this long is an essay for Long reads
NEWS=re.compile(r"\bSTAT\b|dive\b|health affairs|endpoints|financial times|wall street journal|economist|semafor|axios|reuters",re.I)      # news publishers: their pieces stay in the themes
def essay(a):
    """True for an essay that belongs in Long reads: a newsletter or blog piece (Stratechery, Money Stuff, The Diff, Benedict Evans, Out-Of-Pocket, Fintech Takes, Brainfood,
    Import AI, In the Pipeline, the Substacks) of at least ESSAY_WORDS words, not a news publisher's, not an article read in full, not a daily newsletter or a run of short stories."""
    if a.get('fulltext') or a.get('daily') or a.get('unit') or a.get('gap') or a['words']<ESSAY_WORDS or NEWS.search(a.get('source') or ''): return False
    return not multi_story(a['html'])


# Long reads: these publications always take its slots first whenever they arrived, in this order, matched on the piece's source and author (Money Stuff, mailed
# under Bloomberg, also by the series name its subject opens with); never on words inside a title, so an essay quoting "Money Stuff" gets no slot. The editor fills the rest.
LONG_READS_FIRST = (('Stratechery', r"^stratechery\b|\bben thompson\b"), ('Money Stuff', r"\bmatt levine\b|^money stuff\b"), ('The Diff', r"^the diff\b|\bbyrne hobart\b"))
def long_read_rank(a):
    """A piece's place in LONG_READS_FIRST, or None for any other publication."""
    keys=(a.get('source') or '',a.get('author_raw') or a.get('author') or '',re.sub(r':.*','',a.get('title') or '') if ':' in (a.get('title') or '') else '')
    return next((n for n,(_,pat) in enumerate(LONG_READS_FIRST) if any(re.search(pat,k.strip(),re.I) for k in keys)),None)

CHATTER_WORDS=300      # a Long reads piece shorter than this is a post, not an essay
CHATTER=re.compile(r"book club|open thread|discussion thread|\bama\b|ask me anything|mailbag",re.I)      # social posts: reader chatter, whatever their length
def chatter(a):
    """True for a Long reads piece that is not an essay: a social post by its title (CHATTER: a book club chapter, an open thread) or any piece under CHATTER_WORDS words.
    It never takes a Long reads slot; it is an Also today line."""
    return a['words']<CHATTER_WORDS or bool(CHATTER.search(a.get('title') or ''))

# The reader's sources by importance, told to every model run that ranks or selects.
READER_SOURCES = "The reader's most important sources are Stratechery, Money Stuff (Matt Levine) and The Diff; then FT, WSJ, Bloomberg, The Economist and STAT reporting."

def story_blocks(body):
    """The story blocks of a newsletter's cleaned body, each a list of its top-level elements in order: one per h2 headline (with what follows it up to the next h2 or
    rule), else one per brief paragraph (The Economist's briefs), else one per segment between rules. [] when the newsletter has no such structure."""
    kids=[c for c in body.children if getattr(c,'name',None)]
    for tag in ('h2','h3'):
        heads=[c for c in kids if c.name==tag]
        if len(heads)>=2:
            out=[]; cur=None
            for c in kids:
                if c.name==tag: cur=[c]; out.append(cur)
                elif c.name in ('hr','h2') and tag=='h3' or c.name=='hr': cur=None
                elif cur is not None: cur.append(c)
            return out
    briefs=[c for c in kids if c.name=='p' and 'brief' in (c.get('class') or [])]
    if len(briefs)>=2: return [[c] for c in briefs]
    if any(c.name=='hr' for c in kids):
        out=[[]]
        for c in kids:
            if c.name=='hr': out.append([])
            else: out[-1].append(c)
        out=[b for b in out if b]
        return out if len(out)>=2 else []
    return []


def figures_supported(text, source):
    """True when every number in `text` is stated in `source` as a whole number (1,500 is one figure; "3, 4" is two): a figure the source never states is an invention."""
    thousands = lambda x: re.sub(r'(?<=\d),(?=\d{3}(?!\d))', '', x)
    plain = thousands(source)
    return all(re.search(rf'(?<![\d.]){re.escape(n)}(?![\d]|\.\d)', plain) for n in re.findall(r'\d[\d.]*\d|\d', thousands(text)))
