#!/usr/bin/env python3
"""Bouw een NL-gidsbestand voor TiviMate uit meerdere gratis XMLTV-bronnen, onder de zender-ID's van de IPTV-aanbieder.
usage: epg_merge.py <werkmap> <uitvoer.xml.gz>
Leest EPG_PROVIDER_URL uit de omgeving (anders epg_provider_url.txt naast dit script). Print nooit de URL.
Per zender wordt de bron met de meeste dagen/beschrijvingen gekozen; bronnen in SOURCES staan op volgorde van voorkeur."""
import sys, os, re, json, gzip, unicodedata, urllib.request, urllib.parse, html
HERE=os.path.dirname(os.path.abspath(__file__)); work=sys.argv[1]; out=sys.argv[2]
os.makedirs(work, exist_ok=True)
SOURCES=[  # (naam, url, prefix-die-weg-moet)
    ('iptv-epg', 'https://iptv-epg.org/files/epg-nl.xml.gz', r'^NL\s*-\s*'),
    ('epgshare', 'https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz', ''),
    ('open-epg', 'https://www.open-epg.com/files/netherlands.xml.gz', ''),
]
purl=os.environ.get('EPG_PROVIDER_URL','').strip() or open(os.path.join(HERE,'epg_provider_url.txt')).read().strip()
q=urllib.parse.urlparse(purl); base=f"{q.scheme}://{q.netloc}"; creds=dict(urllib.parse.parse_qsl(q.query))
def get(url):
    req=urllib.request.Request(url, headers={'User-Agent':'TiviMate/5.3'})
    with urllib.request.urlopen(req, timeout=240) as r: data=r.read()
    if data[:2]==b'\x1f\x8b': data=gzip.decompress(data)
    return data.decode('utf-8','ignore')
SC=str.maketrans('ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ','abcdefghijklmnopqrstuvwxyz')
def norm(s, strip=''):
    s=html.unescape(unicodedata.normalize('NFKD', s)).translate(SC)
    if strip: s=re.sub(strip,'',s)
    s=re.sub(r'^\s*NL\s*[^A-Za-z0-9]*','',s); s=re.sub(r'[◉].*$','',s)
    s=re.sub(r'(?i)\b(hd|fhd|uhd|sd|4k|8k|raw|fullhd|nl)\b',' ',s)
    return re.sub(r'[^a-z0-9]+','', s.lower())
def aliases(k):
    yield k
    for a in (k+'1', k[:-1] if k.endswith('1') else None, k.replace('tv',''), k.replace('channel',''),
              k.replace('ngc','nationalgeographic'), k.replace('uhd',''), k.replace('kids','junior'), k.replace('xd','')):
        if a and a!=k: yield a
# 1. bronnen laden: per bron -> {normnaam: (cid, icon, [programmes], days, descs)}
sources={}
for name,url,strip in SOURCES:
    try: X=get(url)
    except Exception as e: print(f"bron {name} overgeslagen: {e}"); continue
    chans={}
    for cid,b in re.findall(r'<channel id="([^"]*)">(.*?)</channel>', X, re.S):
        icon=(re.search(r'<icon src="([^"]*)"', b) or [None,None])[1]
        for dn in re.findall(r'<display-name[^>]*>(.*?)</display-name>', b):
            chans.setdefault(norm(dn,strip), (cid, icon))
    progs={}
    for m in re.finditer(r'<programme ([^>]*)>(.*?)</programme>', X, re.S):
        attrs, body = m.group(1), m.group(2)
        cid=re.search(r'channel="([^"]*)"', attrs).group(1)
        progs.setdefault(cid, []).append((re.sub(r'\s*channel="[^"]*"','',attrs), body))
    sources[name]={'chans':chans,'progs':progs}
    print(f"bron {name}: {len(chans)} zendernamen, {sum(len(v) for v in progs.values())} programma's")
def quality(name, cid):
    ps=sources[name]['progs'].get(cid, [])
    days=len({re.search(r'start="(\d{8})',a).group(1) for a,_ in ps if re.search(r'start="(\d{8})',a)})
    desc=sum(1 for _,b in ps if '<desc' in b)
    return (days, desc, len(ps))
# 2. aanbieder: live streams + categorieën
api=f"{base}/player_api.php?username={creds['username']}&password={creds['password']}"
cats={c['category_id']:c['category_name'] for c in json.loads(get(api+"&action=get_live_categories"))}
streams=json.loads(get(api+"&action=get_live_streams"))
nl=[s for s in streams if str(cats.get(str(s.get('category_id')),'')).startswith('NL')]
# 3. koppelen: beste bron per zender
chan_out=[]; prog_out=[]; used=set(); matched=0; nomatch=[]; noid=0; per_source={}
for s in nl:
    name=s.get('name',''); eid=(s.get('epg_channel_id') or '').strip(); k=norm(name)
    best=None
    for srcname,url,strip in SOURCES:
        if srcname not in sources: continue
        for a in aliases(k):
            hit=sources[srcname]['chans'].get(a)
            if hit:
                qd=quality(srcname, hit[0])
                if qd[2]>0 and (best is None or qd>best[0]): best=(qd, srcname, hit)
                break
    if not best: nomatch.append(name); continue
    if not eid: noid+=1; continue
    matched+=1
    if eid in used: continue
    used.add(eid); qd,srcname,(cid,icon)=best; per_source[srcname]=per_source.get(srcname,0)+1
    ic=f'<icon src="{html.escape(icon)}"/>' if icon else ''
    chan_out.append(f'<channel id="{html.escape(eid)}"><display-name>{html.escape(html.unescape(name))}</display-name>{ic}</channel>')
    for attrs, body in sources[srcname]['progs'].get(cid, []):
        prog_out.append(f'<programme {attrs} channel="{html.escape(eid)}">{body}</programme>')
xml='<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="mibox epg_merge v2">\n'+'\n'.join(chan_out)+'\n'+'\n'.join(prog_out)+'\n</tv>\n'
with gzip.open(out,'wb') as f: f.write(xml.encode('utf-8'))
print(f"NL-streams: {len(nl)}; gekoppeld: {matched} (unieke id's: {len(used)}); zonder epg-id: {noid}; niet gekoppeld: {len(nomatch)}")
print("per bron gekozen:", per_source); print("programma's:", len(prog_out), "->", out, os.path.getsize(out)//1024, "KB")
open(os.path.join(work,'niet_gekoppeld.txt'),'w').write('\n'.join(nomatch))
