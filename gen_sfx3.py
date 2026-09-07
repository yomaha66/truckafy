"""Round-4 sounds: searing guitar licks for line ends -> assets/"""
import os, subprocess, eleven
SFX = {
  "lick_dive": ("screaming 1980s hair metal electric guitar solo lick ending in a whammy bar dive bomb, high gain, arena reverb, short", 3, False, 0.7),
  "lick_shred": ("lightning fast shredding electric guitar run climbing up the neck ending on a screaming pinch harmonic squeal, 80s metal, high gain", 3, False, 0.7),
  "lick_squeal": ("single sustained screaming pinch harmonic on distorted electric guitar with wide vibrato, 80s arena metal", 2.5, False, 0.7),
  "lick_stab": ("heavy palm muted power chord stab on distorted electric guitar then a screaming bend, 80s metal, tight", 2, False, 0.7),
}
for name, (prompt, secs, loop, infl) in SFX.items():
    mp3 = eleven.sfx_mp3(prompt, secs, loop, infl)
    tmp = "/tmp/%s.mp3" % name; open(tmp, "wb").write(mp3)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmp, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", os.path.join("assets", name + ".wav")], check=True)
    print("ok", name, len(mp3))
