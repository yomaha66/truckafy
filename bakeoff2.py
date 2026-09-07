"""Round 2: remix each round-1 voice DEEPER, re-render full mix -> listen/deep_N.mp3"""
import json, os, shutil, eleven, main
SAMPLE = ("Sunday! Sunday! Sunday! Monster trucks invade the dome! Grave Digger! Bigfoot! Side by side racing, "
          "car crushing, and the fire breathing jet car! We'll sell you the whole seat, but you'll only need the edge! "
          "Kids seats are still five bucks! Be there!")
DEMO = "Sunday, Sunday, Sunday! Hey Julie, can you grab dog food for Jasper on the way home? We are almost out."

CHANGE = ("Make the voice MUCH deeper: a booming bass-baritone with massive chest resonance, gruffer, rougher, "
          "far more gravel and rasp, hyper-masculine, older and heavier, like a pro wrestling ring announcer "
          "crossed with a monster truck rally announcer. Keep the full-volume shouting stadium energy and add "
          "more dynamic swings: big build-ups, stretched words, hard stops.")
old = json.load(open("bakeoff.json"))
shutil.copy("bakeoff.json", "bakeoff_round1.json")
new = []
for i, vid in enumerate(old, 1):
    prev = eleven.remix_previews(vid, CHANGE, SAMPLE, strength=0.7)[0]
    try:
        nvid = eleven.create_voice("TRUCKAFY deep%d" % i, CHANGE, prev["generated_voice_id"])
    except Exception as e:
        print("create failed (%s) -> deleting round-1 voice %s and retrying" % (str(e)[:80], vid))
        eleven.delete_voice(vid)
        nvid = eleven.create_voice("TRUCKAFY deep%d" % i, CHANGE, prev["generated_voice_id"])
    new.append(nvid)
    pcm = "/tmp/deep_%d.pcm" % i
    open(pcm, "wb").write(eleven.tts_pcm24k(DEMO, nvid))
    main.master(pcm, "listen/deep_%d.mp3" % i, DEMO, 0.8, use_music=True)
    print("rendered listen/deep_%d.mp3 voice=%s" % (i, nvid))
json.dump(new, open("bakeoff.json", "w"))
