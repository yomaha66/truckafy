# TRUCK-A-FY — notes for Claude

Read HANDOFF.md first: state, pipeline, verdicts, next tasks.

## Non-negotiables
- User text is read verbatim. Emphasis (CAPS, stretched vowels, audio tags, glitch edits, repeating the user's own
  words) yes; word changes no. `test_script.py` guards this and must pass after any `script.py` change.
- The sound is signed off. `RECIPE` in `main.py` and the chain in `mix.py` change only when Kevin asks, and then as
  2–3 short A/B variants he can listen to. Unless the sound *is* the task, `selftest.py`'s MP3 must come out
  byte-identical before and after a change (md5 it).
- No air horns, no crash sounds, one extreme rev per clip as punctuation.
- Never print, log, or commit API keys. `ELEVENLABS_API_KEY` and `ELEVEN_VOICE_ID` live in `.env` (gitignored and
  gcloudignored); `deploy.sh` sources it. To check a value, compare a hash or a length, never the value itself.
- Claude cannot hear audio. Renders go to Kevin as files; his verdict decides.

## Working loop
Everything lives and runs on this machine: `C:\Users\ABS\repos\truckafy`, Windows, Git Bash. ElevenLabs, the live
service and `gcloud` are all reachable from here. There is no sandbox and no Cloud Shell step any more.
1. Edit here. After any `mix.py` / `video.py` / `script.py` change, both must pass:
   `./.venv/Scripts/python.exe selftest.py` and `./.venv/Scripts/python.exe test_script.py`.
   (`python3` on this box is the bare 3.14 install without the deps; use the venv. Set `PYTHONIOENCODING=utf-8`
   when printing non-ASCII.)
2. Commit and push to GitHub (`yomaha66/truckafy`). That is the backup; there is no other copy.
3. Deploy: `./deploy.sh 2>&1 | grep -v -i key`. Needs `gcloud` on PATH (any terminal opened after 2026-09-07 has
   it). Cloud Build takes several minutes. Then `curl -s <url>/health` and confirm the revision moved.
4. A real render spends ElevenLabs characters (~150–250 each, Starter tier). Ask before spending.
5. Tell Kevin what changed in one or two sentences and hand him the file.

## Layout
- `main.py` Flask app (`/`, `/truckafy`, `/health`), rate limiter, `RECIPE`
- `script.py` text → performance script · `eleven.py` ElevenLabs client · `mix.py` post-production ·
  `edit.py` word-accurate mixer (behind `mix.render_words` / `render_n`; not routed by `main.py` yet) ·
  `logo.py` pixel wordmark · `video.py` MP4
- `selftest.py` offline pipeline smoke test · `test_script.py` verbatim-rule tests
- `static/index.html` web app · `assets/` SFX · `fonts/` · `takes/` raw takes for offline work
- `deploy.sh`, `Dockerfile`, `.gcloudignore`, `.env` + `.env.example` — Cloud Run, us-central1
  (2 CPU, 2 GiB, concurrency 2, 300 s; one gunicorn worker so the in-memory per-IP limiter is the real limit)
