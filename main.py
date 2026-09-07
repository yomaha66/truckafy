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

DEFAULT_VOICE = os.environ.get("TTS_VOICE", "Algenib")   # gravelly
VOICES = {"Algenib", "Charon", "Fenrir", "Orus", "Puck", "Enceladus",
          "Iapetus", "Alnilam", "Gacrux", "Sadaltager", "Zubenelgenubi"}

ANNOUNCER_PROMPT = (
    "You are a vein-popping 1990s monster truck rally radio announcer screaming into a "
    "distorted microphone at the Pontiac Silverdome. Read the text between the triple "
    "quotes EXACTLY as written — do not add, remove, or change a single word, and do not "
    "read the quotes. Deliver mundane, everyday phrases (groceries, dentist appointments, "
    "taking out the trash) with catastrophic, world-ending intensity: deep chest growls, "
    "extreme vocal strain, rising volume through every sentence, and slam the FINAL WORD "
    "of every sentence like it is the name of the event. Take a hard dramatic pause at "
    "every comma and period.\n\n"
)

INTROS = [
    "THIS SUNDAY AT THE DOME! ",
    "ONE NIGHT ONLY! BE THERE OR BE SQUARE! ",
    "BEWARE! BEWARE! BEWARE! ",
    "KIDS SEATS ARE STILL FIVE BUCKS! ",
]


def synthesize(text: str, voice: str) -> bytes:
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
            asset = "v8_rev.wav" if alt % 2 == 0 else "stadium_airhorn.wav"
            alt += 1
            hits.append((asset, at, 0.55 * g))
    # grand finale on the last word
    end_at = (trailing[0][0] if trailing else dur) - 0.05
    hits.append(("pyro_explosion.wav", max(end_at, 0), 1.0 * g))
    hits.append(("glass_shatter.wav", max(end_at + 0.15, 0), 0.7 * g))
    hits.append(("stadium_airhorn.wav", max(end_at + 0.05, 0), 0.6 * g))
    if intensity > 0.6:  # opening rev before the first word
        hits.append(("v8_rev.wav", 0.0, 0.5 * g))
    return hits, dur


def master(raw_pcm_path, out_path, text, intensity, use_music=True):
    """Full FFmpeg chain. raw_pcm_path is s16le/24k/mono."""
    inten = max(0.0, min(1.0, float(intensity)))
    # --- layer 1.5: pitch & formant drop (-2 .. -4 semitones, formants follow)
    pitch = 2 ** (-(2.0 + 2.0 * inten) / 12)
    # --- layer 2: V-EQ + saturation
    drive_db = 4 + 8 * inten
    # --- layer 3: slapback echo
    fb = 0.30 + 0.20 * inten
    # --- layer 4: music bed level
    music_db = -14 + 6 * inten

    # first pass: voice-only processing to a WAV, so silence detection sees the
    # performance (pauses) rather than the echo tail.
    voice_wav = raw_pcm_path + ".voice.wav"
    run(["ffmpeg", "-y", "-hide_banner", "-f", "s16le", "-ar", "24000", "-ac", "1",
         "-i", raw_pcm_path, "-af",
         f"rubberband=pitch={pitch:.4f}:tempo=1.0:pitchq=quality,"
         "aresample=44100", "-ar", "44100", voice_wav])

    hits, vdur = stage_sfx(text, voice_wav, inten)
    tail = 1.6  # let the echo + finale ring out
    total = vdur + tail

    inputs = ["-i", voice_wav]
    if use_music:
        inputs += ["-stream_loop", "-1", "-i", os.path.join(ASSETS, "heavy_metal_loop.wav")]
    for asset, _at, _g in hits:
        inputs += ["-i", os.path.join(ASSETS, asset)]

    f = []
    # voice chain
    f.append(
        "[0:a]"
        "equalizer=f=150:t=q:w=1.0:g=4,"
        "equalizer=f=800:t=q:w=1.2:g=-3,"
        "equalizer=f=4000:t=q:w=1.0:g=6,"
        f"volume={drive_db:.1f}dB,asoftclip=type=tanh:threshold=0.55:output=0.9,"
        f"aecho=0.8:0.9:180|360|540:{fb:.2f}|{fb*0.55:.2f}|{fb*0.3:.2f},"
        "vibrato=f=0.5:d=0.012,"
        f"apad=pad_dur={tail},atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
        "asplit=2[v][vsc]"
    )
    mix_in = ["[v]"]
    n_in = 1
    if use_music:
        f.append(
            f"[1:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={music_db:.1f}dB,"
            "afade=t=out:st=%.3f:d=1.2[m]" % (total - 1.2)
        )
        # duck the bed -12 dB whenever the voice speaks (fast attack, quick release)
        f.append("[m][vsc]sidechaincompress=threshold=0.03:ratio=12:attack=10:release=180:makeup=1[md]")
        mix_in.append("[md]")
        n_in = 2
    else:
        f.append("[vsc]anullsink")
    for i, (asset, at, gain) in enumerate(hits):
        idx = n_in + i
        f.append(f"[{idx}:a]volume={gain:.2f},adelay={int(at*1000)}|{int(at*1000)}[s{i}]")
        mix_in.append(f"[s{i}]")
    f.append(
        "".join(mix_in) + f"amix=inputs={len(mix_in)}:duration=first:dropout_transition=0:normalize=0,"
        # mastering: loudness-war compressor + brickwall limiter
        "acompressor=threshold=-16dB:ratio=6:attack=4:release=90:makeup=6,"
        "alimiter=limit=0.97:attack=3:release=40:level=false,"
        "aformat=channel_layouts=stereo[out]"
    )
    cmd = ["ffmpeg", "-y", "-hide_banner"] + inputs + [
        "-filter_complex", ";".join(f), "-map", "[out]",
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
