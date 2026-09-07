"""Search the ElevenLabs shared voice library for ready-made monster-truck/hype announcers; build listen/library.html of previews (free)."""
import os, json, urllib.request, urllib.parse, html
KEY = os.environ["ELEVENLABS_API_KEY"]
QUERIES = ["monster truck", "monster truck announcer", "sunday sunday sunday", "hype announcer", "arena announcer",
           "wrestling announcer", "screaming announcer", "raspy announcer", "90s commercial announcer", "movie trailer voice", "stadium announcer", "promo", "rock radio", "raspy", "gravelly", "aggressive", "energetic", "intense", "sports announcer", "ring announcer", "carnival barker", "auctioneer", "drill sergeant", "redneck", "southern announcer", "radio imaging", "over the top", "loud"]
seen = {}
for q in QUERIES:
    url = "https://api.elevenlabs.io/v1/shared-voices?" + urllib.parse.urlencode({"search": q, "page_size": 50, "language": "en"})
    req = urllib.request.Request(url, headers={"xi-api-key": KEY})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=60))
    except Exception as e:
        print("fail", q, e); continue
    for v in d.get("voices", []):
        seen.setdefault(v["voice_id"], v)
vs = sorted(seen.values(), key=lambda v: v.get("cloned_by_count", 0), reverse=True)
txt = " ".join
keep = [v for v in vs if any(k in (v.get("name","")+" "+v.get("description","")+" "+str(v.get("use_case",""))+" "+str(v.get("descriptive",""))).lower()
        for k in ("monster","truck","announcer","hype","scream","shout","wrestl","arena","stadium","trailer","raspy","gravel","intense","epic"))]
def score(v):
    t = (v.get("name","")+" "+(v.get("description") or "")+" "+str(v.get("descriptive",""))+" "+str(v.get("use_case",""))).lower()
    w = {"monster":6,"truck":6,"raspy":4,"gravel":4,"scream":4,"shout":4,"hype":3,"intense":3,"aggressive":3,"rock":2,"promo":2,"announcer":2,"wrestl":3,"arena":2,"stadium":2,"over the top":3,"energetic":2,"loud":2,"redneck":3,"southern":1,"barker":3,"trailer":1}
    return sum(p for k,p in w.items() if k in t) + min(v.get("cloned_by_count",0),100000)/100000
keep = sorted(keep, key=score, reverse=True)[:45]
json.dump([{k: v.get(k) for k in ("voice_id","public_owner_id","name","description","preview_url","cloned_by_count","gender","age","accent","use_case","descriptive","free_users_allowed")} for v in keep], open("library.json","w"), indent=1)
rows = []
for i, v in enumerate(keep, 1):
    rows.append('<div style="margin:14px 0;padding:10px;border:1px solid #ccc;border-radius:8px"><b>%d. %s</b> <small>(%s %s %s, cloned %s, free ok: %s)</small><br><small>%s</small><br><audio controls preload="none" src="%s" style="width:100%%"></audio></div>' % (
        i, html.escape(v.get("name","")), v.get("gender",""), v.get("age",""), v.get("accent",""), v.get("cloned_by_count",0), v.get("free_users_allowed"), html.escape((v.get("description") or "")[:220]), v.get("preview_url","")))
open("listen/library.html","w").write('<!doctype html><meta name=viewport content="width=device-width"><body style="font-family:sans-serif;max-width:760px;margin:24px auto;padding:0 16px"><h2>Voice library candidates (say the NUMBER)</h2>' + "".join(rows) + '</body>')
print(len(vs), "found,", len(keep), "kept -> listen/library.html")
for i, v in enumerate(keep[:15], 1):
    print(i, v.get("name"), "|", v.get("gender"), v.get("age"), "| cloned", v.get("cloned_by_count"), "|", (v.get("description") or "")[:70])
