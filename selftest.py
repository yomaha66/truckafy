"""Offline self-test: runs the full FFmpeg mastering chain on a synthetic
stand-in voice (no Gemini call). Usage: python selftest.py [out.mp3]"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main

SR = 24000
rng = np.random.default_rng(3)
def word(d):
    n = int(SR * d); t = np.arange(n) / SR; f = 110 + rng.uniform(-20, 30)
    return (2 * ((f * t) % 1) - 1) * 0.4 * np.sin(np.pi * np.arange(n) / n)
seq = []
def phrase(k):
    for _ in range(k):
        seq.append(word(rng.uniform(0.15, 0.35))); seq.append(np.zeros(int(SR * 0.06)))
phrase(2); seq.append(np.zeros(int(SR * 0.35)))
phrase(5); seq.append(np.zeros(int(SR * 0.45)))
phrase(5); seq.append(np.zeros(int(SR * 0.3)))
sig = np.concatenate(seq)
raw = "/tmp/truckafy_fake.pcm"
open(raw, "wb").write((sig * 32767).astype(np.int16).tobytes())
out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/truckafy_selftest.mp3"
hits, vdur = main.master(raw, out, "Hey mom, can you feed the cat. Also pick up oat milk!", 0.8)
print(f"OK voice={vdur:.2f}s sfx={len(hits)} -> {out}")
for h in hits: print("  ", h)
