# TRUCK-A-FY  handoff packet

Written 2026-09-07 for continuing the build in Claude Code. Everything below is the current truth of the project; nothing is aspirational unless marked "next".

## 1. What this is

A gag app: type a mundane message, get it back as an extreme 1990s/early-2000s monster-truck-rally radio/TV commercial. The audio is the product; the UI is secondary. End goal: distribute through the App Store as a simple gag app.

Reference sound (the target, per Kevin: "this is what we need"): the 2002 Monster Jam Skydome TV spot  https://www.youtube.com/watch?v=f3QNVbTSkKk (index 11 in playlist PL7RP5jxF6QVaN-6pAvUMOBaBrfEwt3PU8). Style lineage: the Jan Gabriel / Steve Evans "screamer era"  booming, hoarse, relentless; side-by-side drag racing, car crushing, mud bogging, fire-breathing jet cars, "five bucks a kid", "we'll sell you the whole seat but you'll only need the edge."

Hard rules:
- The user's words are read 100% verbatim. Never add, remove, or change a word. Emphasis tricks (CAPS, stretched vowels like "HOOOME!", audio tags) are fine; text changes are not.
- The arena intro ("SUNDAY! SUNDAY! SUNDAY!") is an optional prefix (`arena_prefix: true`), not the default.
- Nothing polite. If it sounds like a radio DJ, it's wrong.

## 2. Where everything lives

- Code: `~/truckafy` in Google Cloud Shell, GCP project `gen-lang-client-0287073066` ("Monster truck voice"). Older scaffold in `~/truckafy_old_*` (dead).
- Cloud Run: service `truckafy-engine`, us-central1, https://truckafy-engine-363682438916.us-central1.run.app  deployed Sep 6 with the OLD Gemini-only build. Everything below has NOT been redeployed.
- TTS: ElevenLabs (primary), Gemini `gemini-2.5-flash-preview-tts` voice Algenib (fallback only  Kevin rejected it as "wayyyy too polite").
- ElevenLabs account: free tier as of Sep 7. 10,000 credits/month (~10 min), 3 custom voice slots, ALL THREE USED by "TRUCKAFY deep1/deep2/deep3". No commercial license on free  Starter ($5/mo) is required before the App Store and gives 10 voice slots. PCM output needs Pro; we request `mp3_44100_128` and decode with ffmpeg.
- Voice IDs: `bakeoff.json` (current three). `bakeoff_round1.json` holds the round-1 IDs, which were deleted to free slots  dead.

Environment variables:

```
GEMINI_API_KEY        fallback TTS (key was pasted in a chat once  rotate before shipping)
ELEVENLABS_API_KEY    required
ELEVEN_VOICE_ID       pick one from bakeoff.json
TTS_BACKEND           eleven | gemini   (defaults to eleven when ELEVENLABS_API_KEY is set)
ELEVEN_MODEL          default eleven_v3
APP_SECRET            optional; enables X-Truckafy-Key header auth on /truckafy
```

## 3. File map

| File | Status | What it is |
|---|---|---|
| `main.py` | live | Flask app. `POST /truckafy`  `synthesize()`  `master()`  MP3. Holds `ANNOUNCER_PROMPT` + `INTROS` (Gemini path), `stage_sfx()` (punctuation  SFX placement), `master()` (FFmpeg chain). |
| `eleven.py` | live | ElevenLabs client (urllib, no SDK): `hype()` text prep, `tts_mp3/tts_pcm24k`, `sfx_mp3`, `design_previews`, `remix_previews`, `create_voice`, `delete_voice`. |
| `bakeoff.py` | done | Round 2: designed 3 voices, rendered `listen/mix_1..3.mp3`. Runs on import  do not `from bakeoff import` anything. |
| `bakeoff2.py` | done | Round 3: remixed each round-2 voice deeper, rendered `listen/deep_1..3.mp3`, wrote `bakeoff.json`. |
| `gen_sfx.py` | done | Generated every `assets/*.wav` with ElevenLabs sound generation. |
| `gen_assets.py` | DEAD | Old sine-wave/noise synthesizer for SFX. **Dockerfile still runs it at image build  this must be removed and real `assets/` shipped instead.** |
| `design_voice.py` | superseded | Round-1 single-voice design (cartoonish result, rejected). |
| `selftest.py` | live | Runs the full FFmpeg chain on a fake voice, no API calls. Use it after any `master()` edit. |
| `listen/` | live | Listening room. `build.py` regenerates `index.html` from the mp3s (newest first). Served by `python3 -m http.server 8080` + Cloud Shell Web Preview. |
| `deploy.sh` | stale | `gcloud run deploy`  only passes GEMINI_API_KEY; needs the ElevenLabs vars. |
| `Dockerfile` | stale | See gen_assets.py note. |
| `flutter_app/` | untouched | Scaffold only; never compiled. |
| `assets/` | live | 7 WAVs, 44.1k stereo: heavy_metal_loop, engine_bed, crowd_bed (12 s loops); v8_rev, stadium_airhorn, pyro_explosion, glass_shatter (hits). Air horn is no longer referenced. |
| `assets_synth_backup/` | delete | The old synthesized junk. |
| `main.py.bak_*` | delete | Backups from the Sep 67 session. |

## 4. Audio pipeline as it stands

1. Text prep  `eleven.hype()`: one `[shouts]` cue up front, tag varies per sentence (`[shouts]` / `[excited][shouts]`), last word of each sentence uppercased with its first vowel tripled ("HOOOME!", "OOOUT!"), sentences joined with " ... " for hard dramatic pauses. Words untouched.
2. TTS  ElevenLabs `eleven_v3`, `stability 0.0` (most expressive/erratic), `similarity_boost 0.6`, speaker boost on. Decoded to s16le/24 kHz/mono so the rest of the chain is backend-agnostic.
3. Pre-pass (ffmpeg, only when intensity > 0): resample 44.1k; rubberband pitch shift of 4intensity semitones; octave-down copy low-passed at 220 Hz mixed under at (14 + 8intensity) dB for chest; written as f32 WAV.
4. `stage_sfx()`: `silencedetect` (32 dB, 0.22 s) finds the real pauses; punctuation maps to hits  `. ! ?`  pyro + car-crush, `,`  V8 rev, finale  pyro + crush + rev, opening rev at t=0 when intensity > 0.3. Air horns removed (Kevin: "no car horns").
5. `master()` filter graph: voice EQ (+5 @110, +3 @250, 2 @900, +3 @3000), drive (8i dB) into tanh soft-clip, arena echo (45/110/230/420/700 ms taps), three sidechain-ducked beds  metal riff (14+6i dB, duck 12:1), engine (12+10i dB, duck 4:1), crowd (20+8i dB, duck 4:1)  hits via `adelay`, `amix`, compressor (16 dB, 6:1), limiter 0.97, MP3 192k.

Request body: `{"text": str, "arena_prefix": bool, "intro": int|null, "intensity": 0..1, "voice": str, "music": bool}`. Note `voice` only applies to the Gemini path today.

## 5. Kevin's verdicts, in order

1. First Gemini render with synthesized SFX bed: "complete and total ass garbage."
2. Gemini with screamer prompt, clean: "wayyyy too polite," needs 150% more extreme, engines revving, "completely off the rails, on the verge of unhinged."
3. ElevenLabs round 1 (voice designed as "unhinged", every sentence ALL CAPS + `[shouts]`): rejected  cartoonish.
4. Round 2 (designed as "professional broadcast VO, deep, hoarse, not cartoonish", full mix): "a bit better," needs more variance, voice deeper and more masculine.
5. Round 3 (remixed deeper, 3.2 st pitch, sub layer, stability 0, stretched words): voice should land **between** the deep one and the higher-pitched round-2 one; **no air horns** (done); **revs could go even higher** (raised  verify); wants **glitching / repeating / slash cuts on certain words**.

Nobody but Kevin has heard any of these clips. Claude cannot listen to audio; every iteration is render  Kevin listens  words back. Keep clips  15 s and render 23 variants per round so each listen decides something.

## 6. Next tasks, in priority order

1. **Voice between round 2 and round 3.** Two independent knobs; expose both as request params so they're tunable without redeploy:
   - Voice model: remix the current deep voice back toward round 2 (`remix_previews(voice_id, "slightly less deep, a touch brighter, same gravel and energy", SAMPLE, strength0.35)`), or design fresh with a description halfway between `bakeoff.py` DESC and `bakeoff2.py` CHANGE. Slots are full  delete one deep voice first.
   - Post: `pitch_semitones` (currently 4i; try 2i) and `sub_db` (try 3 dB from current).
2. **Glitch / stutter / slash cuts on accented words.** Get word timings from ElevenLabs `POST /v1/text-to-speech/{voice_id}/with-timestamps` (character-level alignment  word onsets). Targets: the stretched final word of each sentence, plus the first word of the intro. Effects, sample-accurate in numpy on the 44.1k float voice track *before* the master graph:
   - stutter: repeat the word's first 90140 ms 23 with rising gain and 810 ms fades ("SU-SU-SUNDAY!");
   - slash cut: 2540 ms hard gate right before the word, optionally a 60 ms reversed slice leading in;
   - tape-stop / pitch-dive on the very last word (rubberband tempo ramp or `asetrate` sweep).
   24 events per clip max; more reads as a broken file. Make the count scale with intensity.
3. **Revs.** Confirm the raised levels read as "more"; add a second engine variant (rev-up-and-hold) and pick randomly per hit so consecutive commas don't sound identical. `gen_sfx.py` shows how.
4. **Redeploy.** Remove `gen_assets.py` from the Dockerfile and ship `assets/`; add `ELEVENLABS_API_KEY`, `ELEVEN_VOICE_ID`, `TTS_BACKEND` to `deploy.sh`; `POST` a test; enable `APP_SECRET` before anything public; rotate the Gemini key.
5. **Then** the Flutter app. Not before the audio is signed off.

## 7. How to run

Cloud Shell (everything installed: ffmpeg with rubberband, google-genai, Flask):

```bash
cd ~/truckafy
export ELEVENLABS_API_KEY=...   # never paste keys into a chat
export ELEVEN_VOICE_ID=$(python3 -c "import json;print(json.load(open('bakeoff.json'))[0])")

# offline chain test, no API calls
python3 selftest.py /tmp/st.mp3

# render one clip end to end
PYTHONPATH=. python3 - <<'EOF'
import eleven, main
T = "Sunday, Sunday, Sunday! Hey Julie, can you grab dog food for Jasper on the way home? We are almost out."
open("/tmp/v.pcm","wb").write(eleven.tts_pcm24k(T))
main.master("/tmp/v.pcm", "listen/try.mp3", T, 0.8, use_music=True)
EOF
python3 listen/build.py

# listening room (then Web Preview -> port 8080 in the Cloud Shell toolbar)
(cd listen && nohup python3 -m http.server 8080 >/tmp/http.log 2>&1 &)
```

Local Mac instead: `brew install ffmpeg` (Homebrew's build includes rubberband), `pip install -r requirements.txt`, same env vars, then `open listen/try.mp3` plays instantly  this is the fastest listen loop available.

## 8. Moving to Claude Code

```bash
# in Cloud Shell, ~/truckafy
git init && git add -A && git commit -m "TRUCK-A-FY engine: ElevenLabs v3 + FFmpeg chain, handoff state"
gh auth login            # once
gh repo create truckafy --private --source=. --push
# on the Mac
git clone git@github.com:<you>/truckafy.git && cd truckafy && claude
```

First message to Claude Code:

> Read HANDOFF.md and CLAUDE.md, then do task 1 from section 6: give me three variants of the announcer voice between round 2 and round 3  (a) current deep voice with pitch 2 semitones and sub 3 dB, (b) the deep voice remixed 35% back toward "slightly less deep, a touch brighter", (c) both  rendered as full mixes on the Jasper dog-food line into listen/. Don't touch the Flutter app.

## 9. Known bugs / debts

- `Dockerfile` regenerates synthesized junk into `assets/` at build (`gen_assets.py`). Remove.
- `bakeoff.py` runs its whole flow at import time.
- `voice` request param is ignored on the ElevenLabs path.
- `flutter_app/` has never been built.
- Gemini key rotation pending.
- Backups and `assets_synth_backup/` should be deleted once the repo exists.
