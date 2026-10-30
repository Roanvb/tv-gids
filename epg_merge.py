#!/usr/bin/env python3
"""Bouw een NL-gidsbestand voor TiviMate: epgshare01-programma's onder de zender-ID's van de IPTV-aanbieder.
usage: epg_merge.py <werkmap> <uitvoer.xml.gz>   (leest EPG_PROVIDER_URL uit de omgeving, anders epg_provider_url.txt naast dit script; print nooit de URL)"""
import sys, os, re, json, gzip, io, unicodedata, urllib.request, urllib.parse, html
HERE=os.path.dirname(os.path.abspath(__file__)); work=sys.argv[1]; out=sys.argv[2]
os.makedirs(work, exist_ok=True)
purl=os.environ.get('EPG_PROVIDER_URL','').strip()
if not purl:
    purl=open(os.path.join(HERE,'epg_provider_url.txt')).read().strip()
q=urllib.parse.urlparse(purl); base=f"{q.scheme}://{q.netloc}"; creds=dict(urllib.parse.parse_qsl(q.query))
def get(url, binary=False):
    req=urllib.request.Request(url, headers={'User-Agent':'TiviMate/5.3'})
    with urllib.request.urlopen(req, timeout=180) as r: data=r.read()
    if data[:2]==b'\x1f\x8b': data=gzip.decompress(data)
    return data if binary else data.decode('utf-8','ignore')
SMALLCAPS=str.maketrans('ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ','abcdefghijklmnopqrstuvwxyz')
def norm(s):
    s=html.unescape(unicodedata.normalize('NFKD', s)).translate(SMALLCAPS)
    s=re.sub(r'^\s*NL\s*[^A-Za-z0-9]*','',s)          # 'NL ▎' prefix
    s=re.sub(r'[◉].*$','',s)                            # '◉ rec'
    s=re.sub(r'(?i)\b(hd|fhd|uhd|sd|4k|8k|raw|fullhd|nl)\b',' ',s)
    return re.sub(r'[^a-z0-9]+','', s.lower())
# 1. epgshare NL
E=get("https://epgshare01.online/epgshare01/epg_ripper_NL1.xml.gz")
ech=re.findall(r'<channel id="([^"]*)">(.*?)</channel>', E, re.S)
enames={}
for cid,b in ech:
    for dn in re.findall(r'<display-name[^>]*>(.*?)</display-name>', b): enames.setdefault(norm(dn), cid)
eicons={cid:(re.search(r'<icon src="([^"]*)"', b) or [None,None])[1] for cid,b in ech}
progs={}
for m in re.finditer(r'<programme ([^>]*)>(.*?)</programme>', E, re.S):
    attrs, body = m.group(1), m.group(2)
    cid=re.search(r'channel="([^"]*)"', attrs).group(1)
    progs.setdefault(cid, []).append((re.sub(r'\s*channel="[^"]*"','',attrs), body))
# 2. aanbieder: live streams + categorieën
api=f"{base}/player_api.php?username={creds['username']}&password={creds['password']}"
cats={c['category_id']:c['category_name'] for c in json.loads(get(api+"&action=get_live_categories"))}
streams=json.loads(get(api+"&action=get_live_streams"))
nl=[s for s in streams if str(cats.get(str(s.get('category_id')),'')).startswith('NL')]
# 3. koppelen
chan_out=[]; prog_out=[]; used=set(); matched=0; nomatch=[]; noid=0
for s in nl:
    name=s.get('name',''); eid=(s.get('epg_channel_id') or '').strip()
    k=norm(name); ecid=enames.get(k)
    if not ecid:
        for alt in (k+'1', k[:-1] if k.endswith('1') else None, k.replace('tv',''), k.replace('channel',''),
                    k.replace('ngc','nationalgeographic'), k.replace('uhd','')):
            if alt and alt in enames: ecid=enames[alt]; break
    if not ecid: nomatch.append(name); continue
    if not eid: noid+=1; continue
    matched+=1
    if eid in used: continue
    used.add(eid)
    icon=f'<icon src="{eicons[ecid]}"/>' if eicons.get(ecid) else ''
    chan_out.append(f'<channel id="{html.escape(eid)}"><display-name>{html.escape(html.unescape(name))}</display-name>{icon}</channel>')
    for attrs, body in progs.get(ecid, []):
        prog_out.append(f'<programme {attrs} channel="{html.escape(eid)}">{body}</programme>')
xml='<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="mibox epg_merge">\n'+'\n'.join(chan_out)+'\n'+'\n'.join(prog_out)+'\n</tv>\n'
with gzip.open(out,'wb') as f: f.write(xml.encode('utf-8'))
print(f"NL-streams: {len(nl)}; op naam gekoppeld aan epgshare: {matched} (uniek id: {len(used)}); zonder epg-id: {noid}; niet gekoppeld: {len(nomatch)}")
print("programma's geschreven:", len(prog_out), "->", out, os.path.getsize(out)//1024, "KB")
open(os.path.join(work,'niet_gekoppeld.txt'),'w').write('\n'.join(nomatch))
