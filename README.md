# TRUCK-A-FY

Type a boring message, get it back as a 1990s monster-truck-rally radio commercial.

## Backend (Cloud Run)
- `main.py` — Flask service. `POST /truckafy` → mastered MP3.
  Body: `{"text": "...", "arena_prefix": true, "intro": 0-3, "intensity": 0-1, "voice": "Algenib", "music": true}`
- `gen_assets.py` — synthesizes the metal bed + pyro/glass/airhorn/V8 SFX at image build time.
- `selftest.py` — runs the FFmpeg chain offline on a fake voice (no Gemini call).
- `deploy.sh` — `export GEMINI_API_KEY=...` then `./deploy.sh`. Writes the URL to `.service_url`.
- `smoke.sh` — hits the live service, saves `test.mp3`.

Env vars: `GEMINI_API_KEY` (required), `TTS_MODEL`, `TTS_VOICE`, `APP_SECRET` (optional — clients must send `X-Truckafy-Key`).

## Flutter app
```
cd flutter_app && flutter create . --platforms=ios,android && flutter pub get
flutter run --dart-define=API_URL=https://truckafy-engine-XXXX-uc.a.run.app
```
