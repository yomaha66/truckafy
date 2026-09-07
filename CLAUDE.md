# TRUCK-A-FY — notes for Claude

Read HANDOFF.md first: state, pipeline, verdicts, next tasks.

## Non-negotiables
- User text is read verbatim. Emphasis (CAPS, stretched vowels, audio tags, glitch edits, repeating the user's own
  words) yes; word changes no.
- The sound is signed off. `RECIPE` in `main.py` and the chain in `mix.py` change only when Kevin asks, and then as
  2–3 short A/B variants he can listen to.
- No air horns, no crash sounds, one extreme rev per clip as punctuation.
- Never print, log, or commit API keys. `ELEVENLABS_API_KEY` and `ELEVEN_VOICE_ID` come from env vars only.
- Kevin never touches Cloud Shell. Deliver renders as files in chat; drive Cloud Shell from the browser yourself.

## Working loop
1. Edit in the sandbox clone. `python3 selftest.py` must pass after any `mix.py` / `video.py` / `script.py` change.
2. Anything needing ElevenLabs or the live service runs in Cloud Shell (`~/truckafy`); move code there as a
   base64 patch in ≤12-line chunks, md5-check, `git am`, push. Pull back into the sandbox from GitHub.
3. Deploy with `./deploy.sh 2>&1 | grep -v -i key`, then `curl` a real render and check `x-truckafy-seconds`.
4. Tell Kevin what changed in one or two sentences and hand him the file.

## Layout
- `main.py` Flask app (`/`, `/truckafy`, `/health`), rate limiter, `RECIPE`
- `script.py` text → performance script · `eleven.py` ElevenLabs client · `mix.py` post-production · `logo.py` pixel wordmark · `video.py` MP4
- `static/index.html` web app · `assets/` SFX · `fonts/` · `takes/` raw takes for offline work
- `deploy.sh`, `Dockerfile`, `.gcloudignore` — Cloud Run (2 CPU, 2 GiB, concurrency 2, 300 s)
