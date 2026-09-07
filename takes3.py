"""Raw ElevenLabs takes WITH character timestamps -> takes/<name>.mp3 + takes/<name>.align.json
Run in Cloud Shell (needs ELEVENLABS_API_KEY / ELEVEN_VOICE_ID). The mixer's word-accurate edits are developed
offline against these files, so no API calls are needed while tuning."""
import json, sys, eleven, script

MSGS = {
    "couch_a": ("Jasper, get off the couch. You are not a lap dog.", "first", 1),
    "couch_b": ("Jasper, get off the couch. You are not a lap dog.", "first", 2),
    "demo_sunday": ("Hey Julie, can you grab dog food for Jasper on the way home? We are almost out.", "arena", 0),
    "long3": ("Reminder: dentist appointment Tuesday at 3. Don't forget to floss. Also the dog needs a bath and we are out of milk.", "arena", 5),
    "oneliner": ("Bring the truck around back.", "none", 3),
}
SCRIPTS = {"demo_sunday": "[shouts] Sunday, Sunday, SUUUNDAY! ... [excited][shouts] Hey Julie, can you grab dog food for Jasper on the way HOOOME! ... [shouts] We are almost OOOUT!"}
only = sys.argv[1:]
meta = {}
for name, (msg, intro, seed) in MSGS.items():
    if only and name not in only:
        continue
    if name in SCRIPTS:
        perf, intro_line = SCRIPTS[name], "Sunday, Sunday, SUUUNDAY!"
    else:
        perf, intro_line = script.build(msg, intro=intro, seed=seed, with_intro=True)
    mp3, alignment = eleven.tts_with_timestamps(perf)
    open(f"takes/{name}.mp3", "wb").write(mp3)
    json.dump({"text": msg, "intro": intro, "intro_line": intro_line, "script": perf, "alignment": alignment},
              open(f"takes/{name}.align.json", "w"))
    meta[name] = perf
    print(name, len(mp3), "bytes |", perf)
