# TRUCK-A-FY — project state

Updated 2026-09-07. Everything here is current truth; nothing is aspirational unless it is under "Next".

## 1. What this is

A gag app: type a mundane message, get it back as an extreme 1990s/early-2000s monster-truck-rally TV/radio
commercial, as a share-ready MP4. The audio is the product; the UI is secondary. End goal: App Store distribution.

Reference sound (Kevin: "this is what we need"): the 2002 Monster Jam Skydome TV spot
https://www.youtube.com/watch?v=f3QNVbTSkKk (index 11 in playlist PL7RP5jxF6QVaN-6pAvUMOBaBrfEwt3PU8). Jan Gabriel /
Steve Evans "screamer era": booming, hoarse, relentless, on the verge of unhinged.

Hard rules:
- The user's words are read 100% verbatim. Emphasis (CAPS, stretched vowels, audio tags, glitch edits, repeating the
  user's own words) yes; adding, removing or changing words no. `test_script.py` checks this offline.
- No air horns. No crash sounds. Engines revving, yes — but one extreme rev as punctuation, not "bashing".
- Nothing polite. If it sounds like a radio DJ, it's wrong.
- Keys never appear in chat, logs, or the repo. They live in `.env` next to the code (gitignored, gcloudignored,
  sourced by `deploy.sh`) and in the Cloud Run service's env vars. `.env.example` shows the shape.

## 2. Status

- **Sound: signed off** ("N", 2026-09-07). The recipe is `RECIPE` in `main.py`, applied by `mix.render()`.
  `eleven_v3`, stability 0.
- **Voice: UNRESOLVED as of 2026-09-07.** The live service runs `9j4ISnHLMYhLPWFfFz9S` ("TRUCKAFY deep1"). This
  file used to say the signed-off voice was `mtrellq69YZsNwzUSyXh` (shared-library "Rex Thunder - Deep N Tough",
  saved in My Voices as "TRUCKAFY rex"), and `takes.py` / `takes2.py` still hardcode that id. Section 5's verdicts
  name Rex Thunder. Nobody has confirmed which voice "N" was heard on. Kevin listens to the live site and settles
  it; until then `.env` keeps what prod runs.
- **Product: live.** Cloud Run service `truckafy-engine`, us-central1,
  https://truckafy-engine-363682438916.us-central1.run.app (also in `.service_url` after a deploy). `/` serves the
  web app, `/truckafy` renders MP3 or MP4. Measured: ~12 s for MP3, ~24 s for MP4 (ElevenLabs is most of it).
  Current revision: `gcloud run revisions list --service truckafy-engine --region us-central1`. Revision 00006 was
  deployed 2026-09-07 from this machine at commit `71f87a4`; 00005 before it was built from `7f4e1f4`. Cloud Run
  also answers on https://truckafy-engine-noyulnf4qq-uc.a.run.app (what `deploy.sh` writes to `.service_url`).
- **Look:** `LOGO_STYLE` selects the palette (`fire` | `chrome` | `ice`). Prod runs `chrome` (blue); every default in
  the repo is `fire` (orange), so a local run looks different from prod unless `LOGO_STYLE=chrome` is set.
- **Front end:** `static/index.html`, one screen, mobile-first. Textarea (200 chars), intro picker, "Truck-a-fy it",
  inline video, Share (Web Share API with the MP4 file — iMessage/AirDrop/etc. on phones; falls back to download),
  Save video, Run it again (new seed), Audio only. Note: "Audio only" is a second, separately billed render with no
  seed, so it is a different performance from the video, not the video's soundtrack.
- **Abuse controls:** 200-char cap, 5/min and 40/day per IP (in-memory, per instance; one gunicorn worker per
  instance since 2026-09-07 so those numbers are real — with two workers they were double). `APP_SECRET` header auth
  available but off (empty).
- **ElevenLabs account:** paid, Starter tier. `mp3_44100_128` is the best output format on Starter. Each render is
  ~150–250 characters; 83k remained on 2026-09-07.
- **Repo:** public, github.com/yomaha66/truckafy. Working copy: `C:\Users\ABS\repos\truckafy`.

## 3. Pipeline (one request)

1. `script.build(text, intro, seed, with_intro=True)` → performance script + the intro line.
   `intro=auto` picks the user's first word ×3 two times out of three, else one of the ten `INTROS`. The first word
   must open the message and may be any Unicode letter-word; a message that opens on a number or punctuation gets an
   arena intro instead (nothing is ever invented).
2. `eleven.tts_with_timestamps(perf)` → MP3 bytes + character alignment; `eleven.intro_end_seconds()` finds where the
   intro line ends so the mixer can treat "Sunday, Sunday, SUUUNDAY!" as one segment. Falls back to plain TTS.
3. `mix.render(take, out, seed, intro_end, **RECIPE)` → mastered stereo MP3. Order inside: normalize → merge intro
   → `glitch_middle` (double the first middle phrase if it is under 1.6 s; slash/stutter the accent word of the last
   middle phrase) → `punctuate` (widen the biggest middle pause) → `glitch_finale` (10-semitone riser + word slapback
   on the third intro word, tape-stop on the last word) → `voice_fx` (−2 st, sub layer, EQ, softclip, comp) → slapback
   → reverb → beds ducked under the voice → `schedule_hits` (reverse-rev swell in, siren under the intro, pyro plus a
   rotating rev at intro end, small revs on about half the gaps ≥ 0.14 s, ONE extreme rev after the middle line, pyro
   plus the dragster tires on the finale) → glue → 2-pass loudnorm to −9 LUFS → MP3 192k.
4. `video.make_mp4(mp3, text, out, intro_line)` → Pillow card + ffmpeg `showwaves` → h264/aac, faststart.

`mix.render_words()` / `render_n()` (the word-accurate path through `edit.py`, from the takes4–6 experiments) exist
but are not routed by `main.py`. `edit.py` is in the image since 2026-09-07, so routing them will not crash prod.

## 4. How the work gets done

Everything is on one machine: `C:\Users\ABS\repos\truckafy` (Windows 10, Git Bash, Python 3.14 venv at `.venv`,
ffmpeg 8.1, Google Cloud SDK 583). ElevenLabs and the live service are reachable from here; `gcloud` is authed as
kevin@citizens-finance.com on project `gen-lang-client-0287073066`. The Cowork sandbox and Cloud Shell are no longer
part of the loop (Cloud Shell's `~/truckafy` clone may still exist; nothing depends on it).

- Offline check after any mix/video/script change: `./.venv/Scripts/python.exe selftest.py` (no API calls) and
  `./.venv/Scripts/python.exe test_script.py`. The selftest MP3 should md5-match before and after unless the sound is
  the task. `python3` on this box is the bare interpreter without deps. `librosa` is not installed locally (no
  Python 3.14 wheels yet); `edit.py` degrades gracefully without it.
- Commit and push to GitHub. There is no other copy of the work.
- Deploy: `./deploy.sh 2>&1 | grep -v -i key` from the repo root. It sources `.env`, builds on Cloud Build (several
  minutes) and writes `.service_url`. Then `curl -s <url>/health`.
- Claude cannot hear audio. Every change to the sound is rendered as 2–3 short variants with a one-line description
  of what differs, and Kevin's verdict decides. Real renders spend ElevenLabs characters; ask first.

## 5. Kevin's verdicts (chronological, condensed)

Gemini TTS: "complete and total ass garbage", "wayyyy too polite" → dead. Designed/remixed ElevenLabs voices: rejected
(cartoonish / "absolutely terrible"). Rex Thunder pitched down: good. Round E "the one", F too much (halved the
swings). Background crashing "way too much" → removed; wanted occasional extreme revs, a siren, speedy cheesy guitar.
More guitar, a glitch/repeat in the middle, the rising pitch shift should go "way up", third Sunday gets a dramatic
slapback. K/L: guitar low in the mix is right; needs ONE extreme rev to punctuate a line end. Tires screeching at the
end "was hilarious, bring that back". M/N: approved. Triple-Sunday intro is great but must be switched up, or the
first word of the message gets the triple treatment. Goal restated: super easy, excellent customer experience, type
random messages, get an easy-to-share output.

## 6. Next

1. Settle the voice (section 2). If "N" was signed off on Rex Thunder, set `ELEVEN_VOICE_ID=mtrellq69YZsNwzUSyXh`
   in `.env`, redeploy, and fix `takes.py` / `takes2.py`; if it was deep1, fix those two files the other way.
2. Confirm nothing was left uncommitted in Cloud Shell's `~/truckafy`:
   `gcloud cloud-shell ssh --command="cd ~/truckafy && git status --porcelain"` (interactive terminal the first
   time — it generates an SSH key).
3. App Store wrapper around the web app (PWA/Capacitor or Flutter WebView) — the product is the web page already.
4. Custom domain for the service (truckafy.something) and a proper share preview (OG tags on `/`).
5. Optional polish: more intro lines, a couple of alternate card looks, `format=gif` for platforms that strip video;
   pass the video's seed to "Audio only" so it is the same performance.
6. Before any real traffic: enable `APP_SECRET` if a native client calls the endpoint, watch ElevenLabs character
   usage, consider Cloud Run max-instances.
7. Rotate the old Gemini key (it is no longer used anywhere in the code).
