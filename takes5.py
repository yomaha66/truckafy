"""Register experiment: which ElevenLabs settings/tags give a BRIGHT take like the one N was built from
(pyin median ~150 Hz) instead of the deep reads (95-125 Hz) Kevin hears as 'way too deep'.
4 takes per config on the couch line -> takes/reg_<config>_<n>.mp3 + .align.json"""
import json, sys, eleven

BODY = "Jasper, get off the COOOUCH! ... [shouts] You are not a lap DOOOG!"
CONFIGS = {
    # current build: [shouts] everywhere, stability 0 (Creative)
    "base":     ("[shouts] Jasper, Jasper, JAAASPER! ... [excited][shouts] " + BODY, 0.0),
    # same script, stability 0.5 (Natural) — less variance, maybe a steadier register
    "nat":      ("[shouts] Jasper, Jasper, JAAASPER! ... [excited][shouts] " + BODY, 0.5),
    # push the register up with the tags: screaming intro, frantic excited body
    "scream":   ("[screams] Jasper, Jasper, JAAASPER! ... [excited][shouts][frantic] " + BODY, 0.0),
    # everything shouted AND excited, high energy words in the tags
    "hype":     ("[excited][shouts] Jasper, Jasper, JAAASPER! ... [excited][shouts] " + BODY.replace("[shouts]", "[excited][shouts]"), 0.0),
}
N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
only = sys.argv[2:]
for name, (perf, stab) in CONFIGS.items():
    if only and name not in only:
        continue
    for k in range(N):
        body = {"text": perf, "model_id": eleven.MODEL_TTS,
                "voice_settings": {"stability": stab, "similarity_boost": 0.6, "use_speaker_boost": True}}
        import base64
        data = json.loads(eleven._post("/v1/text-to-speech/" + eleven.VOICE_ID + "/with-timestamps?output_format=mp3_44100_128", body, accept="application/json"))
        mp3 = base64.b64decode(data["audio_base64"]); alignment = data.get("alignment") or data.get("normalized_alignment")
        open(f"takes/reg_{name}_{k}.mp3", "wb").write(mp3)
        json.dump({"text": "Jasper, get off the couch. You are not a lap dog.", "intro": "first", "intro_line": "Jasper, Jasper, JAAASPER!",
                   "script": perf, "stability": stab, "alignment": alignment}, open(f"takes/reg_{name}_{k}.align.json", "w"))
        print(name, k, len(mp3), "bytes")
