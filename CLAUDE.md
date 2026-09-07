# TRUCK-A-FY  project notes for Claude Code

Read HANDOFF.md first. It has the state, the verdicts, and the task list.

## Non-negotiables
- User text is read verbatim. Emphasis (CAPS, stretched vowels, ElevenLabs audio tags, glitch edits) yes; word changes no.
- Audio quality is the product. Do not spend time on the Flutter app until Kevin signs off on the sound.
- Never print, log, or commit API keys. They come from env vars only (`ELEVENLABS_API_KEY`, `GEMINI_API_KEY`).
- Claude cannot hear audio. Every change to the sound must produce files in `listen/` for Kevin to play, and the message to him must say exactly what differs between variants so one listen decides something. Prefer 23 short variants over one long one.

## Working loop
1. Edit `main.py` / `eleven.py`.
2. `python3 selftest.py /tmp/st.mp3`  must pass after any `master()` change (no API cost).
3. Render real variants into `listen/<descriptive_name>.mp3`, then `python3 listen/build.py`.
4. Tell Kevin what to listen for. Wait for his verdict. Record it in HANDOFF.md section 5.

## Costs and limits
- ElevenLabs free tier: 10k credits/month, 3 custom voice slots (full). Each full render of the ~100-char demo line is ~100150 credits; a Voice Design or remix call generates three 30-s previews and is the expensive operation  don't run bake-offs casually.
- Gemini TTS is a fallback only; Kevin rejected its sound.

## Style of the sound (Kevin's words)
"Completely off the rails and on the verge of unhinged." Deep, masculine, gravel; engines revving; no air horns; glitch/stutter/slash cuts on accented words; big dynamic swings, not monotone. Reference: 2002 Monster Jam Skydome TV spot.

## Layout
- `main.py`  Flask + FFmpeg chain (`stage_sfx`, `master`)
- `eleven.py`  ElevenLabs client and text prep (`hype`)
- `assets/`  real SFX/beds (generated once via `gen_sfx.py`; commit them)
- `listen/`  listening room; mp3s are gitignored
- `selftest.py`  offline chain test
- `deploy.sh`, `Dockerfile`  Cloud Run (stale, see HANDOFF.md)
