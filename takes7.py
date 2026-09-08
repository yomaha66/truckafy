"""Nana takes (Sep 8). The env voice the live service and takes3-6 ran on turned out to be "TRUCKAFY deep1"
(9j4ISnHLMYhLPWFfFz9S), not Rex Thunder (mtrellq69YZsNwzUSyXh) that N was signed off on. Same line on both voices,
N's tags vs the R6 direction -> takes/nana_<voice>_<tags>_<k>.mp3 + .align.json"""
import json, base64, eleven

TEXT, INTRO = "Nana, happy birthday", "Nana, Nana, NAAANA!"
VOICES = {"rex": "mtrellq69YZsNwzUSyXh", "deep": "9j4ISnHLMYhLPWFfFz9S"}
TAGS = {
    "n": "[shouts] Nana, Nana, NAAANA! ... [excited][shouts] Nana, happy BIIIRTHDAY!",
    "s": "[screams] Nana, Nana, NAAANA! ... [excited][shouts] Nana, happy BIIIRTHDAY!",
    "r6": "[screams] Nana, Nana, NAAANA! ... [excited][shouts][frantic] Nana, happy BIIIRTHDAY!",
}
JOBS = [("rex", "n", 3), ("rex", "s", 2), ("rex", "r6", 3), ("deep", "r6", 2)]
for vname, tname, n in JOBS:
    for k in range(n):
        perf = TAGS[tname]
        body = {"text": perf, "model_id": eleven.MODEL_TTS,
                "voice_settings": {"stability": 0.0, "similarity_boost": 0.6, "use_speaker_boost": True}}
        data = json.loads(eleven._post("/v1/text-to-speech/" + VOICES[vname] + "/with-timestamps?output_format=mp3_44100_128",
                                       body, accept="application/json"))
        mp3 = base64.b64decode(data["audio_base64"])
        alignment = data.get("alignment") or data.get("normalized_alignment")
        stem = f"takes/nana_{vname}_{tname}_{k}"
        open(stem + ".mp3", "wb").write(mp3)
        json.dump({"text": TEXT, "intro": "first", "intro_line": INTRO, "script": perf, "voice": vname,
                   "stability": 0.0, "alignment": alignment}, open(stem + ".align.json", "w"))
        print(stem, len(mp3), "bytes")
