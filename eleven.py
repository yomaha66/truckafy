"""ElevenLabs backend for TRUCK-A-FY: v3 TTS with audio tags, sound-effects generation, voice design."""
import os, json, re, subprocess, urllib.request, urllib.error

BASE = "https://api.elevenlabs.io"
MODEL_TTS = os.environ.get("ELEVEN_MODEL", "eleven_v3")
VOICE_ID = os.environ.get("ELEVEN_VOICE_ID", "")

def _key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    return k

def _post(path, body, accept="audio/mpeg", timeout=120):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
        headers={"xi-api-key": _key(), "Content-Type": "application/json", "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError("ElevenLabs %s -> %s: %r" % (path, e.code, e.read()[:400]))

VOWELS = "aeiouAEIOU"

def stretch(word):
    """HOME -> HOOOME: stretch the first vowel so the announcer leans on it."""
    for i, ch in enumerate(word):
        if ch in VOWELS:
            return word[:i] + ch * 3 + word[i + 1:]
    return word

def hype(text):
    """Words stay verbatim. Tags vary per sentence, final word of each sentence is CAPS + stretched, ... pauses between."""
    parts = [p for p in re.split(r'(?<=[.!?])\s+', text.strip()) if p]
    out = []
    for i, p in enumerate(parts):
        m = re.match(r"^(.*?)(\b[\w'-]+)([.!?]*)$", p)
        if m:
            last = m.group(2).upper()
            if len(last) > 2:
                last = stretch(last)
            p = m.group(1) + last + "!"
        tag = "[shouts]" if i == 0 else ("[excited][shouts]" if i % 2 else "[shouts]")
        out.append(tag + " " + p)
    return " ... ".join(out)

def tts_mp3(text, voice_id=None):
    vid = voice_id or VOICE_ID
    if not vid:
        raise RuntimeError("ELEVEN_VOICE_ID is not set (run design_voice.py first)")
    body = {"text": hype(text), "model_id": MODEL_TTS,
            "voice_settings": {"stability": 0.0, "similarity_boost": 0.6, "use_speaker_boost": True}}
    return _post("/v1/text-to-speech/" + vid + "?output_format=mp3_44100_128", body)

def tts_mp3_raw(script_text, voice_id=None):
    """TTS of an already-built performance script (no hype() pass). Used by the app endpoint."""
    vid = voice_id or VOICE_ID
    if not vid:
        raise RuntimeError("ELEVEN_VOICE_ID is not set")
    body = {"text": script_text, "model_id": MODEL_TTS,
            "voice_settings": {"stability": 0.0, "similarity_boost": 0.6, "use_speaker_boost": True}}
    return _post("/v1/text-to-speech/" + vid + "?output_format=mp3_44100_128", body)


def tts_pcm24k(text, voice_id=None):
    """Same shape main.synthesize() returns: s16le / 24 kHz / mono."""
    mp3 = tts_mp3(text, voice_id)
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-f", "s16le",
                        "-ar", "24000", "-ac", "1", "pipe:1"], input=mp3, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg decode failed: " + p.stderr.decode()[-300:])
    return p.stdout

def sfx_mp3(prompt, seconds, loop=False, influence=0.6):
    body = {"text": prompt, "duration_seconds": seconds, "prompt_influence": influence, "loop": loop}
    return _post("/v1/sound-generation", body, timeout=180)

def design_previews(description, sample_text):
    body = {"voice_description": description, "text": sample_text, "model_id": "eleven_ttv_v3",
            "guidance_scale": 40, "loudness": 1.0}
    data = json.loads(_post("/v1/text-to-voice/design", body, accept="application/json"))
    return data["previews"]

def create_voice(name, description, generated_voice_id):
    body = {"voice_name": name, "voice_description": description, "generated_voice_id": generated_voice_id}
    data = json.loads(_post("/v1/text-to-voice", body, accept="application/json"))
    return data["voice_id"]

def delete_voice(voice_id):
    req = urllib.request.Request(BASE + "/v1/voices/" + voice_id, method="DELETE", headers={"xi-api-key": _key()})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status

def remix_previews(voice_id, change, sample_text, strength=0.6):
    body = {"voice_description": change, "text": sample_text, "guidance_scale": 30, "loudness": 1.0,
            "prompt_strength": strength}
    data = json.loads(_post("/v1/text-to-voice/" + voice_id + "/remix", body, accept="application/json"))
    return data["previews"]


def tts_with_timestamps(script_text, voice_id=None):
    """Returns (mp3_bytes, alignment) — alignment has characters + character_start/end_times_seconds."""
    import base64
    vid = voice_id or VOICE_ID
    body = {"text": script_text, "model_id": MODEL_TTS,
            "voice_settings": {"stability": 0.0, "similarity_boost": 0.6, "use_speaker_boost": True}}
    data = json.loads(_post("/v1/text-to-speech/" + vid + "/with-timestamps?output_format=mp3_44100_128", body,
                            accept="application/json"))
    return base64.b64decode(data["audio_base64"]), data.get("alignment") or data.get("normalized_alignment")


def intro_end_seconds(script_text, intro_line, alignment):
    """Time at which the intro line finishes, from the character alignment (None if it can't be found)."""
    if not alignment or not intro_line:
        return None
    chars = alignment.get("characters") or []
    ends = alignment.get("character_end_times_seconds") or []
    joined = "".join(chars)
    i = joined.find(intro_line)
    if i < 0:
        i = joined.find(intro_line[-12:])  # tolerate normalization changes at the front
        if i < 0:
            return None
        i -= len(intro_line) - 12
    j = i + len(intro_line) - 1
    return float(ends[j]) if 0 <= j < len(ends) else None
