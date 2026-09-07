"""Design 3 announcer voices, save them, render the FULL mix with each -> listen/mix_N.mp3. Pick one, delete the rest.
Usage: python3 bakeoff.py            (design + render)
       python3 bakeoff.py --keep N   (keep voice N, delete others, write .eleven_voice_id)
"""
import sys, json, os, eleven, main

DESC = (
    "Classic early-2000s American monster truck TV commercial announcer. Deep, powerful, hoarse and gravelly "
    "male voice with huge chest resonance, mid-40s, full-throated shouting projection like yelling over a "
    "stadium PA, aggressive relentless hype, sustained stretched-out words, hard consonants, raspy growl, "
    "professional broadcast voice-over, not cartoonish."
)
SAMPLE = (
    "Sunday! Sunday! Sunday! Monster trucks invade the dome! Grave Digger! Bigfoot! Side by side racing, "
    "car crushing, and the fire breathing jet car! We'll sell you the whole seat, but you'll only need the edge! "
    "Kids seats are still five bucks! Be there!"
)
DEMO = "Sunday, Sunday, Sunday! Hey Julie, can you grab dog food for Jasper on the way home? We are almost out."

if len(sys.argv) > 2 and sys.argv[1] == "--keep":
    keep = int(sys.argv[2]); ids = json.load(open("bakeoff.json"))
    for i, vid in enumerate(ids, 1):
        if i == keep:
            open(".eleven_voice_id", "w").write(vid); print("KEEP", vid)
        else:
            print("delete", vid, eleven.delete_voice(vid))
    sys.exit(0)

prevs = eleven.design_previews(DESC, SAMPLE)
ids = []
for i, p in enumerate(prevs, 1):
    vid = eleven.create_voice("TRUCKAFY v%d" % i, DESC, p["generated_voice_id"])
    ids.append(vid)
    pcm = "/tmp/bake_%d.pcm" % i
    open(pcm, "wb").write(eleven.tts_pcm24k(DEMO, vid))
    main.master(pcm, "listen/mix_%d.mp3" % i, DEMO, 0.7, use_music=True)
    print("rendered listen/mix_%d.mp3 voice=%s" % (i, vid))
json.dump(ids, open("bakeoff.json", "w"))
