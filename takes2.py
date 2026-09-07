"""Generate raw ElevenLabs takes for arbitrary messages through script.build() -> takes/<name>.mp3"""
import json, sys, eleven, script
VID = eleven.VOICE_ID or "mtrellq69YZsNwzUSyXh"
MSGS = {
    "dentist_first": ("Reminder: dentist appointment Tuesday at 3. Don't forget to floss.", "first", 1),
    "birthday_arena": ("Happy birthday Mom, love you! See you Sunday for dinner.", "arena", 2),
    "milk_none": ("Can you pick up milk, eggs, and bread? Also the dog needs a bath.", "first", 3),
}
out = {}
for name, (msg, intro, seed) in MSGS.items():
    perf = script.build(msg, intro=intro, seed=seed)
    mp3 = eleven.tts_mp3_raw(perf, VID)
    open("takes/%s.mp3" % name, "wb").write(mp3)
    out[name] = {"text": msg, "intro": intro, "script": perf}
    print("ok", name, len(mp3), "|", perf[:90])
json.dump(out, open("takes/scripts2.json", "w"), indent=1)
