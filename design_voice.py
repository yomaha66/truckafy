"""Design the TRUCK-A-FY announcer voice on ElevenLabs.
Usage:  python3 design_voice.py            -> writes preview_1.mp3.. + previews.json
        python3 design_voice.py --save N   -> saves preview N as a permanent voice, prints voice_id
"""
import sys, json, base64, eleven

DESC = (
    "Deep, booming, gravel-shredded American male monster truck rally announcer from a 1990s TV commercial, "
    "screaming at the absolute top of his lungs into a distorted stadium PA, voice cracking and straining, "
    "completely unhinged, over the top, rapid-fire hype, thick raspy growl, maximum energy, no restraint."
)
SAMPLE = eleven.hype(
    "Sunday! Sunday! Sunday! This Sunday at the dome! Side by side drag racing, car crushing, mud bogging, "
    "and the fire-breathing jet car! We'll sell you the whole seat, but you'll only need the edge! "
    "Kids seats are still five bucks! Be there!"
)

if len(sys.argv) > 2 and sys.argv[1] == "--save":
    n = int(sys.argv[2])
    prev = json.load(open("previews.json"))
    vid = eleven.create_voice("TRUCKAFY Announcer", DESC, prev[n - 1])
    print("VOICE_ID=" + vid)
    open(".eleven_voice_id", "w").write(vid)
    sys.exit(0)

prevs = eleven.design_previews(DESC, SAMPLE)
ids = []
for i, p in enumerate(prevs, 1):
    open("preview_%d.mp3" % i, "wb").write(base64.b64decode(p["audio_base_64"]))
    ids.append(p["generated_voice_id"])
    print("preview_%d.mp3  %.1fs" % (i, p.get("duration_secs", 0)))
json.dump(ids, open("previews.json", "w"))
print("listen, then: python3 design_voice.py --save N")
