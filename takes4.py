"""Delivery experiments: the same message with different ElevenLabs v3 audio tags -> takes/<name>.mp3 + .align.json
The words never change; only the direction to the announcer does."""
import json, sys, eleven

MSG = "Jasper, get off the couch. You are not a lap dog."
VARIANTS = {
    # the current build: everything shouted
    "couch_shout":  "[shouts] Jasper, Jasper, JAAASPER! ... [excited][shouts] Jasper, get off the COOOUCH! ... [shouts] You are not a lap DOOOG!",
    # hype instead of anger: shout the intro, get excited for the message, shout only the last line
    "couch_hype":   "[shouts] Jasper, Jasper, JAAASPER! ... [excited] Jasper, get off the COOOUCH! ... [excited][shouts] You are not a lap DOOOG!",
    # hype + the announcer cracks himself up at the end
    "couch_laugh":  "[shouts] Jasper, Jasper, JAAASPER! ... [excited] Jasper, get off the COOOUCH! ... [excited][shouts] You are not a lap DOOOG! [laughs]",
    # arena intro instead of the name three times
    "couch_arena":  "[shouts] Sunday, Sunday, SUUUNDAY! ... [excited] Jasper, get off the COOOUCH! ... [excited][shouts] You are not a lap DOOOG!",
    # the demo line, hype version, for a direct comparison with N
    "demo_hype":    "[shouts] Sunday, Sunday, SUUUNDAY! ... [excited] Hey Julie, can you grab dog food for Jasper on the way HOOOME! ... [excited][shouts] We are almost OOOUT!",
}
INTRO = {"couch_shout": "Jasper, Jasper, JAAASPER!", "couch_hype": "Jasper, Jasper, JAAASPER!", "couch_laugh": "Jasper, Jasper, JAAASPER!",
         "couch_arena": "Sunday, Sunday, SUUUNDAY!", "demo_hype": "Sunday, Sunday, SUUUNDAY!"}
only = sys.argv[1:]
for name, perf in VARIANTS.items():
    if only and name not in only:
        continue
    mp3, alignment = eleven.tts_with_timestamps(perf)
    open(f"takes/{name}.mp3", "wb").write(mp3)
    json.dump({"text": MSG if name.startswith("couch") else "Hey Julie, can you grab dog food for Jasper on the way home? We are almost out.",
               "intro": "first", "intro_line": INTRO[name], "script": perf, "alignment": alignment}, open(f"takes/{name}.align.json", "w"))
    print(name, len(mp3), "bytes")
