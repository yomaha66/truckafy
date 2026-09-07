"""Offline self-test: runs the real product pipeline (script -> mix -> video) on a stored take. No API calls.

    python3 selftest.py            # writes /tmp/truckafy_selftest/{truckafy.mp3,truckafy.mp4}
    python3 selftest.py out_dir

Use it after any change to mix.py / video.py / script.py. It exercises the signed-off RECIPE from main.py
on takes/dentist_first.mp3 (a raw ElevenLabs take of "Reminder: dentist appointment Tuesday at 3...").
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mix  # noqa: E402
import script  # noqa: E402
import video  # noqa: E402
from main import RECIPE  # noqa: E402

out_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/truckafy_selftest"
os.makedirs(out_dir, exist_ok=True)
take = os.path.join(HERE, "takes", "dentist_first.mp3")
meta = json.load(open(os.path.join(HERE, "takes", "scripts2.json")))["dentist_first"]

perf, intro_line = script.build(meta["text"], intro=meta["intro"], seed=1, with_intro=True)
print("script:", perf)
assert intro_line.startswith("Reminder") and perf.endswith("FLOOOSS!"), perf
t0 = time.time()
mp3 = os.path.join(out_dir, "truckafy.mp3")
info = mix.render(take, mp3, seed=1, intro_end=None, **RECIPE)
t1 = time.time()
mp4 = video.make_mp4(mp3, meta["text"], os.path.join(out_dir, "truckafy.mp4"), intro_line, tmpdir=out_dir)
t2 = time.time()
assert os.path.getsize(mp3) > 50_000 and os.path.getsize(mp4) > 200_000
print(f"ok  mix {t1 - t0:.1f}s  video {t2 - t1:.1f}s  {info['total_s']}s of audio  ->  {mp3}  {mp4}")
