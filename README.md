# TRUCK-A-FY

Type anything. Get it back as an extreme late-90s monster-truck-rally commercial — your words, read exactly as typed,
by an announcer with zero restraint. Share the MP4.

**Live:** https://truckafy-engine-363682438916.us-central1.run.app/

## How it works

```
text ──► script.py ──► ElevenLabs v3 (Rex Thunder) ──► mix.py ──► MP3 ──► video.py ──► MP4
         delivery      one TTS call, with            numpy/scipy/ffmpeg   Pillow card +
         script only   character timestamps          post-production      waveform
```

* `script.py` never changes a word. It adds an intro line (an arena catchphrase from a pool of ten, or the user's
  own first word three times — "Julie, Julie, JUUULIE!"), puts the last word of each sentence in CAPS with a stretched
  vowel, and inserts ElevenLabs audio tags and " ... " pauses.
* `mix.py` is the signed-off sound: pitch −2 st with an octave-down chest layer, arena convolution reverb, a hair-metal
  riff kept low, engine and crowd beds ducked under the voice, a doppler siren under the intro, an octave riser and
  slapback on the third intro word, the first phrase doubled with a stutter, one extreme rev punctuating the middle
  line, a tape-stop on the last word, and a dragster launch with screaming tires on the way out. Mastered to −9 LUFS.
* `video.py` draws a 1080×1080 card (message, intro line, wordmark) and lets ffmpeg's `showwaves` animate over it.

## API

```
POST /truckafy   {"text": "...", "intro": "auto|first|arena|none", "seed": 123, "format": "mp3|mp4"}
GET  /truckafy?text=...&intro=auto&format=mp3
GET  /health
```

Responses are `audio/mpeg` or `video/mp4`. Headers: `X-Truckafy-Script` (the performance script that was read),
`X-Truckafy-Seconds`. Limits: 200 characters, 5 renders/minute and 40/day per IP. Errors are JSON `{"error": "..."}`
with 400 / 429 / 502.

## Run it

```bash
export ELEVENLABS_API_KEY=...        # never paste keys into a chat
export ELEVEN_VOICE_ID=mtrellq69YZsNwzUSyXh
pip install -r requirements.txt      # plus ffmpeg (with librubberband) on PATH
python3 selftest.py                  # offline: script -> mix -> mp4 on a stored take, no API calls
python3 main.py                      # http://localhost:8080
./deploy.sh                          # Cloud Run, us-central1
```

Env vars: `ELEVENLABS_API_KEY`, `ELEVEN_VOICE_ID`, optional `MAX_CHARS`, `RATE_PER_MIN`, `RATE_PER_DAY`,
`APP_SECRET` (when set, clients must send `X-Truckafy-Key`), `ELEVEN_MODEL` (default `eleven_v3`).

## Layout

| Path | What |
|---|---|
| `main.py` | Flask app: `/`, `/truckafy`, `/health`, rate limiter, the `RECIPE` |
| `script.py` | text → performance script (intros, accents, tags) |
| `eleven.py` | ElevenLabs client (TTS with timestamps, sound generation, voice library) |
| `mix.py` | the post-production chain |
| `video.py` | share card + waveform → MP4 |
| `static/index.html` | the one-screen web app |
| `assets/` | engine/crowd beds, riffs, sirens, revs, pyro (made with `gen_sfx*.py`) |
| `fonts/` | Bangers, Anton, Bebas Neue (OFL) |
| `takes/` | raw ElevenLabs takes for offline recipe work + `selftest.py` |
| `takes.py`, `takes2.py`, `find_voices.py`, `gen_sfx.py`, `gen_sfx2.py` | dev tools that call ElevenLabs |

Fonts are under the SIL Open Font License (`fonts/OFL.txt`).
