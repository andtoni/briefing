import json,re,sys
from bs4 import BeautifulSoup, Comment
BLOCK={'p','h1','h2','h3','h4','blockquote','ul','ol','li','figure','figcaption','hr','pre'}
INLINE_KEEP={'a','em','i','strong','b','sup','sub','code','br','img'}
CONTAINER={'div','table','tbody','thead','tr','td','th','center','section','article','main','header','footer','aside','span_block'}
JUNK=re.compile(r'(unsubscribe|view (this )?(email|in (your )?browser)|read in app|forwarded this|manage (your )?(preferences|subscription)|privacy policy|share this|subscribe now|upgrade to paid|leave a comment|^share$|^subscribe$|get the app|all rights reserved|update your (email )?preferences|sent to you|sign up here|was this (email )?forwarded|read online|^listen (now|on)|^like$|^comment$|^restack$|start writing|pledge your support|refer a friend|^advertisement$|sponsored by|©|reader-supported|consider becoming a (free or )?paid|^for subscribers$|^thanks for reading|is a reader.supported|^read more$|^share .{0,40}$|become a (paid )?subscriber|this post is public|^photo: |^getty images$|^image: )',re.I)
ADIMG=re.compile(r'(pixel|track|/open|beacon|spacer|icon|logo|avatar|button|pas\.economist|doubleclick|/ad[sv]?/|liveintent|emoji|twitter|facebook|linkedin|badge)',re.I)
def clean(html):
    s=BeautifulSoup(html,'lxml')
    for t in s(['script','style','head','meta','link','title','svg','form','button','input','iframe','video','audio','noscript','picture source']): t.decompose()
    for c in s.find_all(string=lambda x:isinstance(x,Comment)): c.extract()
    for t in s.find_all(style=re.compile(r'display:\s*none|max-height:\s*0|font-size:\s*0|visibility:\s*hidden',re.I)): t.decompose()
    for im in s('img'):
        w=im.get('width','');h=im.get('height','');src=im.get('src','')
        small=any(str(v).isdigit() and int(v)<=140 for v in (w,h))
        if small or not src.startswith('http') or ADIMG.search(src): im.decompose()
    for t in list(s.find_all(True)):
        if t.name in ('html','body') or t.name in BLOCK or t.name in INLINE_KEEP: continue
        if t.name in CONTAINER: t.name='div'
        else: t.unwrap()
    for d in s.find_all('div'):
        if not d.find(['div']+list(BLOCK)) and (d.get_text(strip=True) or d.find('img')): d.name='p'
    for d in s.find_all('div'): d.unwrap()
    for t in s.find_all(True):
        t.attrs={k:v for k,v in t.attrs.items() if (t.name=='a' and k=='href') or (t.name=='img' and k in('src','alt'))}
    body=s.body or s
    for p in body.find_all('p'):          # no nested paragraphs
        for q in p.find_all(['p']): q.unwrap()
    for a in body.find_all('a'):
        if not a.get_text(strip=True) and not a.find('img'): a.decompose()
    for t in body.find_all(['p','li','h1','h2','h3','h4','figcaption']):
        tx=t.get_text(' ',strip=True)
        if not tx and not t.find('img'): t.decompose(); continue
        if len(tx)<240 and JUNK.search(tx): t.decompose()
    for t in body.find_all(['ul','ol','blockquote','figure']):
        if not t.get_text(strip=True) and not t.find('img'): t.decompose()
    prev=None                              # drop consecutive duplicates (email heading repeated as alt text)
    for t in body.find_all(['p','h1','h2','h3','h4']):
        tx=re.sub(r'\s+',' ',t.get_text(' ',strip=True))
        if tx and tx==prev and not t.find('img'): t.decompose(); continue
        if tx: prev=tx
    for h in body.find_all('h1'): h.name='h2'
    for h in body.find_all('h4'): h.name='h3'
    out=''.join(str(c) for c in body.children)
    out=re.sub(r'\s+([,.;:!?”’)])',r'\1',re.sub(r'\n\s*\n+','\n',out))
    return out
