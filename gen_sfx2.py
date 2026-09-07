"""Round-3 sounds: siren, extreme revs, speedy cheesy riffs -> assets/"""
import os, subprocess, eleven
SFX = {
  "riff_speedy_a": ("fast cheesy 1980s hair metal electric guitar riff, shredding, high tempo 180 bpm, arena rock, energetic, seamless loop", 12, True, 0.5),
  "riff_speedy_b": ("speedy surf rock distorted electric guitar riff, fast tremolo picking, twangy, cheesy, high energy, seamless loop", 12, True, 0.5),
  "siren_wail": ("police siren wailing, passing by fast with doppler effect, loud", 4, False, 0.7),
  "siren_airraid": ("air raid siren winding up and wailing, loud, outdoor", 4, False, 0.7),
  "rev_extreme_a": ("monster truck engine massive extreme rev, screaming supercharger whine, backfire pops, close up", 3, False, 0.75),
  "rev_extreme_b": ("top fuel dragster engine launch, deafening roar, tires screaming", 3, False, 0.75),
  "rev_extreme_c": ("monster truck revving repeatedly and aggressively, three big revs, exhaust backfire", 4, False, 0.75),
}
for name, (prompt, secs, loop, infl) in SFX.items():
    mp3 = eleven.sfx_mp3(prompt, secs, loop, infl)
    tmp = "/tmp/%s.mp3" % name; open(tmp, "wb").write(mp3)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmp, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", os.path.join("assets", name + ".wav")], check=True)
    print("ok", name, len(mp3))
