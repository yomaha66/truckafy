"""Raw ElevenLabs takes of the demo line with different cadence scripts -> takes/*.mp3 (voice only, no FX)."""
import json, eleven, os
VID = "mtrellq69YZsNwzUSyXh"  # TRUCKAFY rex (Rex Thunder)
TAKES = {
 "t1_baseline": "[shouts] Sunday, Sunday, SUUUNDAY! ... [excited][shouts] Hey Julie, can you grab dog food for Jasper on the way HOOOME! ... [shouts] We are almost OOOUT!",
 "t2_slowmiddle": "[shouts] Sunday! Sunday! SUUUNDAY! ... [excited] Hey Julie... can you GRAB... dog food... for JASPER... on the way... HOOOME?! ... [shouts] We are almost OUUUT!",
 "t3_staccato": "[shouts] SUNDAY! SUNDAY! SUNDAY! [excited][shouts] Hey Julie, can you grab dog food for Jasper, on... the... way... HOOOME! ... [shouts] WE. ARE. ALMOST. OUUUUT!",
 "t4_laugh": "[shouts] Sunday, Sunday, SUUUNDAY! [excited][shouts] Hey Julie, can you grab dog food for Jasper on the way HOOOME?! ... [shouts] We are almost OUUUT! [laughs]",
}
for name, script in TAKES.items():
    body = {"text": script, "model_id": "eleven_v3", "voice_settings": {"stability": 0.0, "similarity_boost": 0.6, "use_speaker_boost": True}}
    mp3 = eleven._post("/v1/text-to-speech/" + VID + "?output_format=mp3_44100_128", body)
    open("takes/rex_%s.mp3" % name, "wb").write(mp3)
    print("ok", name, len(mp3))
json.dump(TAKES, open("takes/scripts.json", "w"), indent=1)
