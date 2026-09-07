"""TRUCK-A-FY engine — turns a mundane message into a 1990s monster-truck-rally
radio commercial.

POST /truckafy  {"text": "...", "arena_prefix": bool, "intro": int|null,
                 "intensity": 0.0-1.0, "voice": "Algenib"}
  -> audio/mpeg (mastered MP3)

Pipeline (per the Gemini spec, 5 layers + mastering):
  1. Gemini TTS, in-character announcer, text read VERBATIM
  2. Pitch/formant drop, V-shaped EQ, tube saturation      (FFmpeg)
  3. Stadium slapback echo + tape-flutter LFO              (FFmpeg)
  4. Heavy-metal bed, sidechain-ducked under the voice     (FFmpeg)
  5. SFX staged onto real pauses in the performance:
       period/!/?  -> pyro + glass      comma/pause -> V8 rev or airhorn
       end of clip -> pyro + airhorn    (silencedetect finds the pauses)
  M. Loudness-war compressor + brickwall limiter -> MP3 192k
"""
import os
import re
import json
import logging
import subprocess
import tempfile
import time

from flask import Flask, request, jsonify, Response
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("truckafy")

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

# ------------------------------------------------------------------ Gemini
_client = None


def client():
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=key)
    return _client


# Candidate TTS models, first that works wins (override with TTS_MODEL env var).
TTS_MODELS = [m for m in [
    os.environ.get("TTS_MODEL"),
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
] if m]
_working_model = None
TTS_BACKEND = os.environ.get("TTS_BACKEND", "eleven" if os.environ.get("ELEVENLABS_API_KEY") else "gemini")

DEFAULT_VOICE = os.environ.get("TTS_VOICE", "Algenib")   # gravelly
VOICES = {"Algenib", "Charon", "Fenrir", "Orus", "Puck", "Enceladus",
          "Iapetus", "Alnilam", "Gacrux", "Sadaltager", "Zubenelgenubi"}

ANNOUNCER_PROMPT = (
    "You are the announcer on a 1980s-1990s monster truck rally radio commercial, in the style of the "
    "classic SUNDAY-SUNDAY-SUNDAY arena screamer ads -- the Jan Gabriel / Steve Evans school of announcing. "
    "Delivery: a huge, booming, gravel-throated baritone pushed to the edge of breaking, enormous lung power, "
    "rapid-fire pace with no dead air. Every sentence climbs in pitch and volume and SLAMS the final word. "
    "Stretch and growl the biggest words (MONNNSTER, CRRRUSHING, SUNNNDAY). Punch every hard consonant. "
    "Sell everything like it is side-by-side drag racing, car crushing, mud bogging, fire-breathing jet car "
    "mayhem -- even when it is groceries or a dentist appointment. Hit a hard dramatic stop at every comma "
    "and period. Never calm, never conversational, never friendly -- this is a man yelling over a stadium PA. "
    "Read the text between the triple quotes EXACTLY as written: do not add, remove, or change a single "
    "word, and do not read the quotes.\n\n"
)

INTROS = [
    "SUNDAY! SUNDAY! SUNDAY! ",
    "THIS SUNDAY AT THE DOME! ",
    "WE'LL SELL YOU THE WHOLE SEAT, BUT YOU'LL ONLY NEED THE EDGE! ",
    "SIDE BY SIDE DRAG RACING! CAR CRUSHING! MUD BOGGING! AND THE FIRE-BREATHING JET CAR! ",
    "ONE NIGHT ONLY! BE THERE OR BE SQUARE! ",
    "BEWARE! BEWARE! BEWARE! ",
    "KIDS SEATS ARE STILL FIVE BUCKS! ",
]


def synthesize(text: str, voice: str) -> bytes:
    if TTS_BACKEND == "eleven":
        try:
            import eleven
            t0 = time.time()
            data = eleven.tts_pcm24k(text)
            log.info("tts ok backend=eleven bytes=%d %.2fs", len(data), time.time() - t0)
            return data
        except Exception as e:  # noqa: BLE001
            log.warning("eleven failed, falling back to gemini: %s", e)
    """Return raw PCM (s16le, 24 kHz, mono) from Gemini TTS."""
    global _working_model
    prompt = ANNOUNCER_PROMPT + '"""' + text + '"""'
    cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
    )
    models = [_working_model] if _working_model else TTS_MODELS
    last_err = None
    for model in models:
        try:
            t0 = time.time()
            resp = client().models.generate_content(model=model, contents=prompt, config=cfg)
            part = resp.candidates[0].content.parts[0]
            data = part.inline_data.data
            if isinstance(data, str):  # some SDK paths hand back base64
                import base64
                data = base64.b64decode(data)
            log.info("tts ok model=%s voice=%s bytes=%d %.2fs", model, voice, len(data), time.time() - t0)
            _working_model = model
            return data
        except Exception as e:  # noqa: BLE001
            log.warning("tts failed model=%s: %s", model, e)
            last_err = e
    raise RuntimeError(f"All TTS models failed: {last_err}")


# ------------------------------------------------------------------ FFmpeg helpers
def run(cmd):
    log.info("ffmpeg: %s", " ".join(cmd[:6]) + " ...")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        log.error(p.stderr[-2000:])
        raise RuntimeError("ffmpeg failed: " + p.stderr[-400:])
    return p.stderr


def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def detect_pauses(path, min_len=0.22, noise_db=-32):
    """Return [(start, end), ...] of silences in the voice track."""
    err = run(["ffmpeg", "-hide_banner", "-i", path, "-af",
               f"silencedetect=noise={noise_db}dB:d={min_len}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    if len(starts) > len(ends):  # silence ran to EOF: no silence_end line
        ends.append(None)
    return list(zip(starts, ends))


def punctuation_marks(text):
    """Ordered list of clause/sentence breaks in the text: 'hard' or 'soft'."""
    marks = []
    for m in re.finditer(r"[.!?]+|[,;:—-]+", text):
        marks.append("hard" if m.group()[0] in ".!?" else "soft")
    return marks


def stage_sfx(text, voice_path, intensity):
    """Map punctuation to real pauses -> list of (asset, time, gain)."""
    pauses = [p for p in detect_pauses(voice_path)]
    dur = probe_duration(voice_path)
    # leading silence is not a break
    pauses = [p for p in pauses if p[0] > 0.15]
    # a trailing pause = the end; handle separately
    trailing = [p for p in pauses if p[1] is None or p[1] >= dur - 0.05]
    inner = [p for p in pauses if p not in trailing]
    marks = punctuation_marks(text.rstrip(".!?, "))
    hits = []
    g = 0.55 + 0.45 * intensity
    alt = 0
    for i, (start, _end) in enumerate(inner):
        kind = marks[i] if i < len(marks) else ("hard" if i % 2 else "soft")
        at = max(start - 0.06, 0)
        if kind == "hard":
            hits.append(("pyro_explosion.wav", at, 0.9 * g))
            hits.append(("glass_shatter.wav", at + 0.12, 0.6 * g))
        else:
            asset = "v8_rev.wav"  # no air horns (Kevin)
            alt += 1
            hits.append((asset, at, 0.85 * g))
    # grand finale on the last word
    end_at = (trailing[0][0] if trailing else dur) - 0.05
    hits.append(("pyro_explosion.wav", max(end_at, 0), 1.0 * g))
    hits.append(("glass_shatter.wav", max(end_at + 0.15, 0), 0.7 * g))
    hits.append(("v8_rev.wav", max(end_at + 0.05, 0), 0.9 * g))
    if intensity > 0.3:  # opening rev before the first word
        hits.append(("v8_rev.wav", 0.0, 0.8 * g))
    return hits, dur


def master(raw_pcm_path, out_path, text, intensity, use_music=True):
    """Full FFmpeg chain. raw_pcm_path is s16le/24k/mono. Everything scales with intensity."""
    inten = max(0.0, min(1.0, float(intensity)))
    pitch = 2 ** (-(4.0 * inten) / 12)
    drive_db = 8 * inten
    fb = 0.25 + 0.25 * inten
    music_db = -14 + 6 * inten
    engine_db = -12 + 10 * inten
    crowd_db = -20 + 8 * inten

    voice_wav = raw_pcm_path + ".voice.wav"
    sub_db = -14 + 8 * inten  # octave-down sub layer = chest
    src = ["ffmpeg", "-y", "-hide_banner", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw_pcm_path]
    if inten > 0:
        fc = (f"[0:a]aresample=44100,asplit=2[m][s];"
              f"[m]rubberband=pitch={pitch:.4f}:tempo=1.0:pitchq=quality[mp];"
              f"[s]rubberband=pitch=0.5:tempo=1.0,lowpass=f=220,volume={sub_db:.1f}dB[sub];"
              f"[mp][sub]amix=inputs=2:duration=first:normalize=0[out]")
        run(src + ["-filter_complex", fc, "-map", "[out]", "-ar", "44100", "-c:a", "pcm_f32le", voice_wav])
    else:
        run(src + ["-af", "aresample=44100", "-ar", "44100", "-c:a", "pcm_f32le", voice_wav])

    hits, vdur = stage_sfx(text, voice_wav, inten)
    tail = 1.8
    total = vdur + tail

    beds = []  # (file, dB, duck ratio)
    if use_music and os.path.exists(os.path.join(ASSETS, "heavy_metal_loop.wav")):
        beds.append(("heavy_metal_loop.wav", music_db, 12))
    for name, db in (("engine_bed.wav", engine_db), ("crowd_bed.wav", crowd_db)):
        if os.path.exists(os.path.join(ASSETS, name)):
            beds.append((name, db, 4))

    inputs = ["-i", voice_wav]
    for name, _, _ in beds:
        inputs += ["-stream_loop", "-1", "-i", os.path.join(ASSETS, name)]
    for asset, _at, _g in hits:
        inputs += ["-i", os.path.join(ASSETS, asset)]

    f = []
    vf = ["[0:a]"]
    if inten > 0:
        vf.append("equalizer=f=110:t=q:w=1.0:g=5,equalizer=f=250:t=q:w=1.2:g=3,equalizer=f=900:t=q:w=1.2:g=-2,equalizer=f=3000:t=q:w=1.0:g=3,")
        vf.append(f"volume={drive_db:.1f}dB,asoftclip=type=tanh:threshold={0.95 - 0.35 * inten:.2f}:output=0.9,")
        vf.append(f"aecho=0.8:0.85:45|110|230|420|700:{fb:.2f}|{fb*0.7:.2f}|{fb*0.5:.2f}|{fb*0.35:.2f}|{fb*0.2:.2f},")
    vf.append(f"apad=pad_dur={tail},atrim=0:{total:.3f},asetpts=PTS-STARTPTS")
    nb = len(beds)
    vf.append((f",asplit={nb + 1}[v]" + "".join(f"[vsc{i}]" for i in range(nb))) if nb else "[v]")
    f.append("".join(vf))
    mix_in = ["[v]"]
    for i, (name, db, ratio) in enumerate(beds):
        f.append(f"[{1 + i}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={db:.1f}dB,"
                 f"afade=t=out:st={total - 1.2:.3f}:d=1.2[b{i}]")
        f.append(f"[b{i}][vsc{i}]sidechaincompress=threshold=0.03:ratio={ratio}:attack=10:release=180:makeup=1[bd{i}]")
        mix_in.append(f"[bd{i}]")
    for i, (asset, at, gain) in enumerate(hits):
        f.append(f"[{1 + nb + i}:a]volume={gain:.2f},adelay={int(at * 1000)}|{int(at * 1000)}[s{i}]")
        mix_in.append(f"[s{i}]")
    f.append("".join(mix_in) + f"amix=inputs={len(mix_in)}:duration=first:dropout_transition=0:normalize=0,"
             "acompressor=threshold=-16dB:ratio=6:attack=4:release=90:makeup=6,"
             "alimiter=limit=0.97:attack=3:release=40:level=false,aformat=channel_layouts=stereo[out]")
    cmd = ["ffmpeg", "-y", "-hide_banner"] + inputs + ["-filter_complex", ";".join(f), "-map", "[out]",
           "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", out_path]
    run(cmd)
    return hits, vdur


# ------------------------------------------------------------------ routes
@app.get("/")
def health():
    return jsonify({"ok": True, "service": "truckafy-engine", "intros": INTROS,
                    "voices": sorted(VOICES), "model": _working_model})


APP_SECRET = os.environ.get("APP_SECRET", "")  # optional: require X-Truckafy-Key header


@app.post("/truckafy")
def truckafy():
    if APP_SECRET and request.headers.get("X-Truckafy-Key") != APP_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()
    if not user_text:
        return jsonify({"error": "No text provided"}), 400
    if len(user_text) > 600:
        return jsonify({"error": "Keep it under 600 characters"}), 400

    use_prefix = bool(data.get("arena_prefix", False))
    intro_idx = data.get("intro")
    intensity = float(data.get("intensity", 0.8))
    voice = data.get("voice") or DEFAULT_VOICE
    if voice not in VOICES:
        voice = DEFAULT_VOICE
    use_music = bool(data.get("music", True))

    if use_prefix:
        try:
            intro = INTROS[int(intro_idx)] if intro_idx is not None else INTROS[len(user_text) % len(INTROS)]
        except (ValueError, IndexError):
            intro = INTROS[0]
        final_text = intro + user_text
    else:
        final_text = user_text

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "voice.pcm")
        out = os.path.join(tmp, "monster_master.mp3")
        try:
            with open(raw, "wb") as fh:
                fh.write(synthesize(final_text, voice))
            hits, vdur = master(raw, out, final_text, intensity, use_music)
        except Exception as e:  # noqa: BLE001
            log.exception("render failed")
            return jsonify({"error": str(e)}), 500
        with open(out, "rb") as fh:
            mp3 = fh.read()
    log.info("rendered %d bytes, voice %.1fs, %d sfx, total %.2fs", len(mp3), vdur, len(hits), time.time() - t0)
    return Response(mp3, mimetype="audio/mpeg", headers={
        "Content-Disposition": 'inline; filename="truckafy.mp3"',
        "X-Truckafy-Text": final_text[:200].encode("ascii", "ignore").decode(),
        "X-Truckafy-SFX": str(len(hits)),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
