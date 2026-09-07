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
  user's own words) yes; adding, removing or changing words no.
- No air horns. No crash sounds. Engines revving, yes — but one extreme rev as punctuation, not "bashing".
- Nothing polite. If it sounds like a radio DJ, it's wrong.
- Keys never appear in chat, logs, or the repo. They live in Cloud Shell `~/.truckafy_env` (mode 600, sourced by
  `.bashrc`) and in the Cloud Run service's env vars.

## 2. Status

- **Sound: signed off** ("N", 2026-09-07). Voice = ElevenLabs shared-library "Rex Thunder - Deep N Tough"
  (`mtrellq69YZsNwzUSyXh`, saved in My Voices as "TRUCKAFY rex"), `eleven_v3`, stability 0. The recipe is
  `RECIPE` in `main.py` and is applied by `mix.render()`.
- **Product: live.** Cloud Run service `truckafy-engine`, us-central1, revision 00003,
  https://truckafy-engine-363682438916.us-central1.run.app (also in `.service_url`). `/` serves the web app,
  `/truckafy` renders MP3 or MP4. Measured: ~12 s for MP3, ~24 s for MP4 (ElevenLabs is most of it).
- **Front end:** `static/index.html`, one screen, mobile-first. Textarea (200 chars), intro picker, "Truck-a-fy it",
  inline video, Share (Web Share API with the MP4 file — iMessage/AirDrop/etc. on phones; falls back to download),
  Save video, Run it again (new seed), Audio only.
- **Abuse controls:** 200-char cap, 5/min and 40/day per IP (in-memory, per instance), `APP_SECRET` header auth
  available but off.
- **ElevenLabs account:** paid, Starter tier. `mp3_44100_128` is the best output format on Starter.
- **Repo:** public, github.com/yomaha66/truckafy.

## 3. Pipeline (one request)

1. `script.build(text, intro, seed, with_intro=True)` → performance script + the intro line.
   `intro=auto` picks the user's first word ×3 two times out of three, else one of the ten `INTROS`.
2. `eleven.tts_with_timestamps(perf)` → MP3 bytes + character alignment; `eleven.intro_end_seconds()` finds where the
   intro line ends so the mixer can treat "Sunday, Sunday, SUUUNDAY!" as one segment. Falls back to plain TTS.
3. `mix.render(take, out, seed, intro_end, **RECIPE)` → mastered stereo MP3. Order inside: normalize → merge intro
   → `glitch_middle` (double the first middle phrase, slash/stutter its accent word) → `punctuate` (widen the biggest
   middle pause) → `glitch_finale` (octave riser + word slapback on the third intro word, tape-stop on the last word)
   → `voice_fx` (−2 st, sub layer, EQ, softclip, comp) → reverb + slapback → beds ducked under the voice →
   `schedule_hits` (reverse-rev swell in, siren under the intro, pyro at intro end, ONE extreme rev after the middle
   line, dragster tires on the finale) → glue → 2-pass loudnorm to −9 LUFS → MP3 192k.
4. `video.make_mp4(mp3, text, out, intro_line)` → Pillow card + ffmpeg `showwaves` → h264/aac, faststart.

## 4. How the work gets done

Kevin does not touch Cloud Shell; Claude drives it through the browser. The Cowork sandbox cannot reach
api.elevenlabs.io or *.run.app, so:
- Mixing, video, and front-end work happen in the sandbox clone of the repo; renders go to Kevin as files in chat.
- TTS takes, SFX generation and deploys happen in Cloud Shell (`~/truckafy`). Code moves sandbox → Cloud Shell as a
  `git format-patch`, gzip+base64, typed into the terminal in ≤12-line heredoc chunks, md5-checked, then `git am`
  and `git push`; sandbox pulls from GitHub. (Typing one long heredoc drops characters.)
- Deploy: in Cloud Shell, `cd ~/truckafy && ./deploy.sh 2>&1 | grep -v -i key`. The Cloud Shell VM recycles; if
  `ffmpeg` is missing, `sudo apt-get install -y ffmpeg`.
- Offline check after any mix/video/script change: `python3 selftest.py` (no API calls).
- Claude cannot hear audio. Every change to the sound is rendered as 2–3 short variants with a one-line description of
  what differs, and Kevin's verdict decides.

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

1. App Store wrapper around the web app (PWA/Capacitor or Flutter WebView) — the product is the web page already.
2. Custom domain for the service (truckafy.something) and a proper share preview (OG tags on `/`).
3. Optional polish: more intro lines, a couple of alternate card looks, `format=gif` for platforms that strip video.
4. Before any real traffic: enable `APP_SECRET` if a native client calls the endpoint, watch ElevenLabs character
   usage (each render is ~150–250 characters), consider Cloud Run max-instances.
5. Rotate the old Gemini key (it is no longer used anywhere in the code).
