"""TRUCK-A-FY engine — turns any typed message into a late-90s monster-truck-rally commercial.

POST /truckafy  {"text": "...", "intro": "auto|first|arena|none", "seed": int|null}  -> audio/mpeg
GET  /truckafy?text=...                                                              -> audio/mpeg
GET  /health

Pipeline: script.build() (delivery only, words verbatim) -> ElevenLabs v3 (Rex Thunder voice, one call)
          -> mix.render() (the signed-off "N" recipe: -2 st + chest layer, arena reverb, octave riser +
          slapback on the third intro word, doubled first phrase + stutter, one punctuation rev, siren,
          low speedy riff, tape-stop + dragster finale) -> MP3 192k stereo, ~-8.5 LUFS.
"""
import collections
import logging
import os
import random
import tempfile
import threading
import time

from flask import Flask, Response, jsonify, request, send_from_directory

import eleven
import mix
import script
import video

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("truckafy")

app = Flask(__name__, static_folder="static", static_url_path="/static")
APP_SECRET = os.environ.get("APP_SECRET", "")
MAX_CHARS = int(os.environ.get("MAX_CHARS", "200"))
PER_MIN = int(os.environ.get("RATE_PER_MIN", "5"))
PER_DAY = int(os.environ.get("RATE_PER_DAY", "40"))

# ---- per-IP limiter (in-memory, per instance; enough to stop a loop or a bored script kid) ----
_hits = collections.defaultdict(list)
_lock = threading.Lock()


def _client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    return (xff.split(",")[0].strip() if xff else request.remote_addr) or "?"


def _limited(ip):
    now = time.time()
    with _lock:
        h = [t for t in _hits[ip] if now - t < 86400]
        _hits[ip] = h
        if sum(1 for t in h if now - t < 60) >= PER_MIN or len(h) >= PER_DAY:
            return True
        h.append(now)
    return False

# the signed-off recipe (round 6, "N")
RECIPE = dict(rise=True, rise_semis=10.0, slap_word=True, glitch_mid=True, tapestop=True, punct=True,
              pitch=-2.0, riff="riff_speedy_a.wav", riff_db=-16.0, engine_db=-17.0, crowd_db=-26.0, lufs=-9.0)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/fonts/<path:name>")
def fonts(name):
    return send_from_directory(os.path.join(app.root_path, "fonts"), name, max_age=31536000)


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "truckafy-engine", "voice": eleven.VOICE_ID or None,
                    "intros": script.INTROS, "max_chars": MAX_CHARS})


def _render(user_text, intro, seed, fmt="mp3"):
    perf, intro_line = script.build(user_text, intro=intro, seed=seed, with_intro=True)
    t0 = time.time()
    intro_end = None
    try:
        take, alignment = eleven.tts_with_timestamps(perf)
        intro_end = eleven.intro_end_seconds(perf, intro_line, alignment)
    except Exception as e:  # noqa: BLE001 — timestamps are a nicety; the plain call is the fallback
        log.warning("with-timestamps failed (%s); plain TTS", str(e)[:120])
        take = eleven.tts_mp3_raw(perf)
    t_tts = time.time() - t0
    with tempfile.TemporaryDirectory() as tmp:
        take_path = os.path.join(tmp, "take.mp3")
        out_path = os.path.join(tmp, "truckafy.mp3")
        with open(take_path, "wb") as fh:
            fh.write(take)
        info = mix.render(take_path, out_path, seed=seed if seed is not None else random.randrange(1 << 30),
                          intro_end=intro_end, **RECIPE)
        if fmt == "mp4":
            out_path = video.make_mp4(out_path, user_text, os.path.join(tmp, "truckafy.mp4"), intro_line, tmpdir=tmp)
        with open(out_path, "rb") as fh:
            blob = fh.read()
    log.info("rendered %s %d bytes | tts %.1fs | total %.1fs | %r", fmt, len(blob), t_tts, time.time() - t0, perf[:120])
    return blob, perf, info


def _handle(user_text, intro, seed, fmt):
    if APP_SECRET and request.headers.get("X-Truckafy-Key") != APP_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    user_text = " ".join((user_text or "").split())
    if not user_text:
        return jsonify({"error": "Type something first."}), 400
    if len(user_text) > MAX_CHARS:
        return jsonify({"error": f"Keep it under {MAX_CHARS} characters."}), 400
    if intro not in ("auto", "first", "arena", "none"):
        intro = "auto"
    fmt = "mp4" if fmt == "mp4" else "mp3"
    ip = _client_ip()
    if _limited(ip):
        return jsonify({"error": "Whoa there. Too many in a row — give the engine a minute."}), 429
    try:
        blob, perf, info = _render(user_text, intro, seed, fmt)
    except Exception as e:  # noqa: BLE001
        log.exception("render failed")
        return jsonify({"error": "The announcer lost his voice. Try again."}), 502
    mime = "video/mp4" if fmt == "mp4" else "audio/mpeg"
    return Response(blob, mimetype=mime, headers={
        "Content-Disposition": f'inline; filename="truckafy.{fmt}"',
        "X-Truckafy-Script": perf[:400].encode("ascii", "ignore").decode(),
        "X-Truckafy-Seconds": str(info["total_s"]),
        "Cache-Control": "no-store",
    })


@app.post("/truckafy")
def truckafy_post():
    data = request.get_json(silent=True) or {}
    seed = data.get("seed")
    return _handle(data.get("text"), data.get("intro", "auto"), int(seed) if seed is not None else None, data.get("format", "mp3"))


@app.get("/truckafy")
def truckafy_get():
    seed = request.args.get("seed")
    return _handle(request.args.get("text"), request.args.get("intro", "auto"), int(seed) if seed else None,
                   request.args.get("format", "mp3"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
