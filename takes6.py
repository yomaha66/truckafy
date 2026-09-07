"""Register experiment 2: intermediate tag configs (the [frantic] family pushed the register from ~100 Hz to ~185 Hz;
the take N was built from sits at 150). 4 takes each on the couch line -> takes/reg2_<config>_<n>.mp3 + .align.json"""
import json, sys, base64, eleven

CONFIGS = {
    "frantic_body": "[shouts] Jasper, Jasper, JAAASPER! ... [excited][shouts][frantic] Jasper, get off the COOOUCH! ... [shouts][frantic] You are not a lap DOOOG!",
    "frantic_all":  "[frantic][shouts] Jasper, Jasper, JAAASPER! ... [frantic][shouts] Jasper, get off the COOOUCH! ... [frantic][shouts] You are not a lap DOOOG!",
    "scream_intro": "[screams] Jasper, Jasper, JAAASPER! ... [excited][shouts] Jasper, get off the COOOUCH! ... [shouts] You are not a lap DOOOG!",
    "manic":        "[manic][shouts] Jasper, Jasper, JAAASPER! ... [manic][excited][shouts] Jasper, get off the COOOUCH! ... [manic][shouts] You are not a lap DOOOG!",
}
N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
for name, perf in CONFIGS.items():
    for k in range(N):
        body = {"text": perf, "model_id": eleven.MODEL_TTS,
                "voice_settings": {"stability": 0.0, "similarity_boost": 0.6, "use_speaker_boost": True}}
        data = json.loads(eleven._post("/v1/text-to-speech/" + eleven.VOICE_ID + "/with-timestamps?output_format=mp3_44100_128", body, accept="application/json"))
        mp3 = base64.b64decode(data["audio_base64"]); alignment = data.get("alignment") or data.get("normalized_alignment")
        open(f"takes/reg2_{name}_{k}.mp3", "wb").write(mp3)
        json.dump({"text": "Jasper, get off the couch. You are not a lap dog.", "intro": "first", "intro_line": "Jasper, Jasper, JAAASPER!",
                   "script": perf, "stability": 0.0, "alignment": alignment}, open(f"takes/reg2_{name}_{k}.align.json", "w"))
        print(name, k, len(mp3), "bytes")
