"""TRUCK-A-FY engine — turns any typed message into a late-90s monster-truck-rally commercial.

POST /truckafy  {"text": "...", "intro": "auto|first|arena|none", "seed": int|null}  -> audio/mpeg
GET  /truckafy?text=...                                                              -> audio/mpeg
GET  /health

Pipeline: script.build() (delivery only, words verbatim) -> ElevenLabs v3 (Rex Thunder voice, one call)
          -> mix.render() (the signed-off "N" recipe: -2 st + chest layer, arena reverb, octave riser +
          slapback on the third intro word, doubled first phrase + stutter, one punctuation rev, siren,
          low speedy riff, tape-stop + dragster finale) -> MP3 192k stereo, ~-8.5 LUFS.
"""
import logging
import os
import random
import tempfile
import time

from flask import Flask, Response, jsonify, request

import eleven
import mix
import script

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("truckafy")

app = Flask(__name__)
APP_SECRET = os.environ.get("APP_SECRET", "")
MAX_CHARS = int(os.environ.get("MAX_CHARS", "280"))

# the signed-off recipe (round 6, "N")
RECIPE = dict(rise=True, rise_semis=10.0, slap_word=True, glitch_mid=True, tapestop=True, punct=True,
              pitch=-2.0, riff="riff_speedy_a.wav", riff_db=-16.0, engine_db=-17.0, crowd_db=-26.0, lufs=-9.0)


@app.get("/")
@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "truckafy-engine", "voice": eleven.VOICE_ID or None,
                    "intros": script.INTROS, "max_chars": MAX_CHARS})


def _render(user_text, intro, seed):
    perf = script.build(user_text, intro=intro, seed=seed)
    t0 = time.time()
    take = eleven.tts_mp3_raw(perf)
    t_tts = time.time() - t0
    with tempfile.TemporaryDirectory() as tmp:
        take_path = os.path.join(tmp, "take.mp3")
        out_path = os.path.join(tmp, "truckafy.mp3")
        with open(take_path, "wb") as fh:
            fh.write(take)
        info = mix.render(take_path, out_path, seed=seed if seed is not None else random.randrange(1 << 30), **RECIPE)
        with open(out_path, "rb") as fh:
            mp3 = fh.read()
    log.info("rendered %d bytes | tts %.1fs | total %.1fs | %r", len(mp3), t_tts, time.time() - t0, perf[:120])
    return mp3, perf, info


def _handle(user_text, intro, seed):
    if APP_SECRET and request.headers.get("X-Truckafy-Key") != APP_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    user_text = (user_text or "").strip()
    if not user_text:
        return jsonify({"error": "No text provided"}), 400
    if len(user_text) > MAX_CHARS:
        return jsonify({"error": f"Keep it under {MAX_CHARS} characters"}), 400
    if intro not in ("auto", "first", "arena", "none"):
        intro = "auto"
    try:
        mp3, perf, info = _render(user_text, intro, seed)
    except Exception as e:  # noqa: BLE001
        log.exception("render failed")
        return jsonify({"error": str(e)[:300]}), 502
    return Response(mp3, mimetype="audio/mpeg", headers={
        "Content-Disposition": 'inline; filename="truckafy.mp3"',
        "X-Truckafy-Script": perf[:400].encode("ascii", "ignore").decode(),
        "X-Truckafy-Seconds": str(info["total_s"]),
        "Access-Control-Allow-Origin": "*",
    })


@app.post("/truckafy")
def truckafy_post():
    data = request.get_json(silent=True) or {}
    seed = data.get("seed")
    return _handle(data.get("text"), data.get("intro", "auto"), int(seed) if seed is not None else None)


@app.get("/truckafy")
def truckafy_get():
    seed = request.args.get("seed")
    return _handle(request.args.get("text"), request.args.get("intro", "auto"), int(seed) if seed else None)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
