"""Generate REAL-sounding SFX + beds with ElevenLabs sound generation, into assets/ (replaces the synthesized junk)."""
import os, subprocess, shutil, eleven
A = "assets"
if not os.path.isdir(A + "_synth_backup"):
    shutil.copytree(A, A + "_synth_backup")
SFX = {
    "heavy_metal_loop":  ("aggressive 1990s arena heavy metal guitar riff, palm muted chugging, double kick drums, distorted, high energy, seamless loop", 12, True, 0.5),
    "engine_bed":        ("monster truck supercharged V8 engine idling and revving, loud, throaty, close up, continuous, seamless loop", 12, True, 0.6),
    "crowd_bed":         ("huge indoor stadium crowd roaring and screaming continuously, arena ambience, seamless loop", 12, True, 0.5),
    "v8_rev":            ("monster truck supercharged V8 engine revving hard once, huge roar, close up", 3, False, 0.7),
    "stadium_airhorn":   ("loud stadium air horn blast, long, echoing in an arena", 2.5, False, 0.7),
    "pyro_explosion":    ("massive pyrotechnic explosion with fireball whoosh and stadium echo", 2.5, False, 0.7),
    "glass_shatter":     ("car being crushed, metal crunching and glass shattering, loud impact", 2, False, 0.7),
}
for name, (prompt, secs, loop, infl) in SFX.items():
    mp3 = eleven.sfx_mp3(prompt, secs, loop, infl)
    tmp = "/tmp/%s.mp3" % name
    open(tmp, "wb").write(mp3)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmp, "-ar", "44100", "-ac", "2",
                    os.path.join(A, name + ".wav")], check=True)
    print("ok", name, len(mp3), "bytes")
