#!/usr/bin/env python3
"""TRUCK-A-FY mixer v2 — numpy + ffmpeg (rubberband) post-production on a raw voice take.

    python3 mix.py takes/rex_t1_baseline.mp3 out.mp3 [--cadence] [--stutter] [--slash] [--tapestop]
                   [--pitch -2] [--engine -17] [--riff -21] [--crowd -26] [--lufs -9]

Everything here is post: the words on the take are never touched. Cadence edits re-time the
MIDDLE of the take (never the first or last phrase), stutters/slash cuts land on accented words.
"""
import argparse, json, os, subprocess, sys
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 44100
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
RNG = np.random.default_rng(7)


# ----------------------------------------------------------------------------- io / helpers
def load(path, sr=SR):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "pipe:1"],
                       capture_output=True, check=True)
    return np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64)


def ff(x, filt, sr=SR):
    """Run an ffmpeg -af chain on a mono float array."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ac", "1", "-ar", str(sr), "-i", "pipe:0",
                        "-af", filt, "-f", "f32le", "-ac", "1", "-ar", str(sr), "pipe:1"],
                       input=x.astype(np.float32).tobytes(), capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[-600:])
    return np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64)


def db(g):
    return 10.0 ** (g / 20.0)


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


def peak_db(x):
    return 20 * np.log10(np.max(np.abs(x)) + 1e-12)


def fade(x, ms_in=5, ms_out=5):
    x = x.copy()
    a = int(SR * ms_in / 1000); b = int(SR * ms_out / 1000)
    if a and len(x) > a:
        x[:a] *= np.linspace(0, 1, a)
    if b and len(x) > b:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def env_follow(x, attack=0.004, release=0.12):
    """Peak envelope follower, returns 0..1-ish linear envelope."""
    y = np.zeros_like(x); a = np.exp(-1 / (SR * attack)); r = np.exp(-1 / (SR * release)); v = 0.0
    ax = np.abs(x)
    for i in range(len(x)):  # vectorising this properly is overkill for 15 s clips
        s = ax[i]
        v = a * v + (1 - a) * s if s > v else r * v + (1 - r) * s
        y[i] = v
    return y


def frame_db(x, hop_ms=10):
    hop = int(SR * hop_ms / 1000); n = len(x) // hop
    e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1))
    return 20 * np.log10(e + 1e-9)


def segments(x, thr_db=-32, min_gap=0.14, min_len=0.08):
    """Speech segments (start, end) in seconds from a 10 ms energy grid."""
    e = frame_db(x); on = e > thr_db; hop = 0.01; gapf = int(min_gap / hop)
    segs = []; i = 0; n = len(on)
    while i < n:
        if on[i]:
            j = i
            while j < n:
                if on[j]:
                    j += 1; continue
                if on[j:j + gapf].any():
                    j += 1; continue
                break
            if (j - i) * hop >= min_len:
                segs.append((i * hop, j * hop))
            i = j
        else:
            i += 1
    return segs


def valleys(x, start, end, smooth_ms=25, min_prom_db=5.0, min_sep=0.16):
    """Envelope valleys inside [start,end] — used as word boundaries. Returns times."""
    e = frame_db(x[int(start * SR):int(end * SR)])
    k = max(1, int(smooth_ms / 10)); ker = np.ones(k) / k
    es = np.convolve(e, ker, mode="same")
    out = []
    for i in range(2, len(es) - 2):
        if es[i] <= es[i - 1] and es[i] <= es[i + 1]:
            left = es[max(0, i - 25):i].max(); right = es[i:i + 25].max()
            if min(left, right) - es[i] >= min_prom_db:
                t = start + i * 0.01
                if not out or t - out[-1] >= min_sep:
                    out.append(t)
    return out


def merge_intro(segs, intro_end):
    """Fold every leading segment that starts before intro_end into one intro segment (timestamps from the TTS)."""
    if not intro_end or len(segs) < 2:
        return segs
    idx = [i for i, (a, b) in enumerate(segs) if a < intro_end + 0.05]
    k = max(idx) if idx else 0
    return [(segs[0][0], segs[k][1])] + segs[k + 1:] if k > 0 else segs


def last_word_onset(x, seg):
    """Onset of the final word in a segment: last envelope valley that leaves >= 0.25 s of word."""
    s, e = seg
    vs = [v for v in valleys(x, s, e) if e - v >= 0.25 and v - s >= 0.15]
    return vs[-1] if vs else None


# ----------------------------------------------------------------------------- edits
def tempo(x, factor):
    """factor > 1 = faster/shorter. rubberband keeps pitch."""
    if abs(factor - 1.0) < 0.02 or len(x) < SR * 0.05:
        return x
    return ff(x, f"rubberband=tempo={factor:.3f}:pitch=1.0:pitchq=quality")


def stutter(word, n=3, slice_ms=115):
    """SU-SU-SUNDAY: repeat the first slice of the word n times with rising gain, then the word."""
    L = int(SR * slice_ms / 1000)
    sl = fade(word[:L], 3, 8)
    parts = [sl * g for g in np.linspace(0.8, 1.05, n)]
    gap = np.zeros(int(SR * 0.018))
    out = []
    for p in parts:
        out += [p, gap]
    out.append(word)
    return np.concatenate(out)


def slash_cut(pre, word, gap_ms=32, rev_ms=55):
    """Hard gate right before the word, led in by a short reversed slice of what came before."""
    r = int(SR * rev_ms / 1000)
    lead = fade(pre[-r:][::-1], 2, 2) * 0.8 if len(pre) > r else np.zeros(0)
    return np.concatenate([pre, lead, np.zeros(int(SR * gap_ms / 1000)), word])


def varispeed(x, factor):
    """Tape-style speed change: factor > 1 = faster AND higher (pitch moves with speed)."""
    if abs(factor - 1.0) < 0.02 or len(x) < 64:
        return x
    n = max(2, int(len(x) / factor))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def sweep(x, st0, st1, curve=1.0):
    """Variable-rate resample: pitch/speed glides from st0 to st1 semitones across the chunk."""
    r0, r1 = 2 ** (st0 / 12), 2 ** (st1 / 12)
    n = int(len(x) / ((r0 + r1) / 2)) + 2
    rate = r0 + (r1 - r0) * (np.linspace(0, 1, n) ** curve)
    pos = np.cumsum(rate); pos = pos[pos < len(x) - 1]
    return np.interp(pos, np.arange(len(x)), x)


def riser(word, semis=4.0, start_frac=0.35):
    """Accent word climbs in pitch and speed toward its end ('SUNDAAAY' going up)."""
    n0 = int(len(word) * start_frac)
    return np.concatenate([word[:n0], sweep(word[n0:], 0.0, semis, curve=1.8)])


def tape_stop(word, start_frac=0.55, dive_s=0.22, floor=0.18):
    """Pitch/tempo dive on the tail of a word (turntable power-off). Fast."""
    n0 = int(len(word) * start_frac)
    head, tail = word[:n0], word[n0:]
    if len(tail) < SR * 0.12:
        return word
    out_len = int(SR * dive_s)
    rate = np.linspace(1.0, floor, out_len) ** 1.6
    pos = np.cumsum(rate)
    pos = pos[pos < len(tail) - 1]
    dived = np.interp(pos, np.arange(len(tail)), tail) * np.linspace(1.0, 0.0, len(pos)) ** 0.7
    return np.concatenate([head, dived])


def cadence_middle(x, segs, seed=3, stutter_on=True, slash_on=True, vari=False, rise=False):
    """Re-time the middle phrases: alternate fast/slow chunks, drop dramatic micro-pauses, stutter accents.
    vari=True uses tape-style varispeed (pitch moves with speed) instead of pitch-preserving tempo.
    rise=True puts a pitch riser on the accent word. First and last segments are left alone."""
    rng = np.random.default_rng(seed)
    speed = varispeed if vari else tempo
    if len(segs) < 3:
        return x, segs
    pieces = [x[:int(segs[0][1] * SR)]]  # intro phrase, untouched
    cursor = segs[0][1]
    for si in range(1, len(segs) - 1):
        s, e = segs[si]
        pieces.append(x[int(cursor * SR):int(s * SR)])  # the gap before this phrase, as is
        # split the phrase into word-ish chunks
        bounds = [s] + valleys(x, s, e) + [e]
        chunks = [x[int(a * SR):int(b * SR)] for a, b in zip(bounds[:-1], bounds[1:])]
        chunks = [c for c in chunks if len(c) > 0]
        # merge fragments shorter than 0.3 s into their predecessor so a "chunk" is a word, not a syllable tail
        merged = []
        for c in chunks:
            if merged and len(c) < SR * 0.3:
                merged[-1] = np.concatenate([merged[-1], c])
            else:
                merged.append(c)
        chunks = merged
        pool = [0.9, 1.14, 0.93, 1.19, 1.0] if vari else [0.86, 1.22, 0.9, 1.3, 1.0]
        factors = rng.choice(pool, size=len(chunks), replace=True)
        for ci, (c, f) in enumerate(zip(chunks, factors)):
            last = ci == len(chunks) - 1
            if last:
                # the accented last word: keep it heavy and hit it with the glitch
                c = speed(c, 0.9)
                if rise:
                    c = riser(c, semis=float(rng.uniform(1.5, 2.5)))
                if slash_on and pieces:
                    prev = pieces.pop()
                    pieces.append(slash_cut(prev, np.zeros(0)))
                if stutter_on and len(chunks) >= 2:  # single-word phrases just get the cut, not a stutter
                    c = stutter(c, n=int(rng.integers(2, 4)))
                pieces.append(c)
            else:
                c = speed(c, float(f))
                if f < 1.0 and rng.random() < 0.6:  # a hitch before a slow chunk
                    pieces.append(np.zeros(int(SR * rng.uniform(0.09, 0.2))))
                pieces.append(c)
        cursor = e
    pieces.append(x[int(cursor * SR):])  # gap + final phrase, untouched
    y = np.concatenate(pieces)
    return y, segments(y)


def word_slap(y, a, b, taps=4, delay=0.19, fb=0.6, level_db=-2.0, tail_frac=0.45):
    """Dramatic slapback on one word: the last syllable ("...DAY") repeats, decaying and darkening,
    laid OVER whatever follows: SUNDAY... day... day... day."""
    n = b - a; t0 = a + int(n * (1 - tail_frac))
    rep = fade(y[t0:b], 6, 20); d = int(SR * delay); out = y.copy()
    rep = ff(rep, "lowpass=f=3600,highpass=f=220")
    for k in range(1, taps + 1):
        g = db(level_db) * (fb ** (k - 1))
        if k > 1:
            rep = ff(rep, "lowpass=f=2400")
        i = b + int(SR * 0.03) + (k - 1) * d; j = min(len(out), i + len(rep))
        if i >= len(out):
            break
        out[i:j] += rep[:j - i] * g
    return out


def glitch_middle(x, segs, seed=3):
    """Glitch/repeat in the middle WITHOUT re-timing: the first middle phrase gets a quick doubled
    repeat (slightly pitched up), and the accent word of the last middle phrase gets a slash cut + stutter."""
    rng = np.random.default_rng(seed)
    if len(segs) < 3:
        return x, segs
    mids = segs[1:-1]
    pieces = [x[:int(mids[0][0] * SR)]]
    cursor = mids[0][0]
    for mi, (s, e) in enumerate(mids):
        pieces.append(x[int(cursor * SR):int(s * SR)])
        w = x[int(s * SR):int(e * SR)]
        if mi == 0 and len(mids) >= 2 and (e - s) < 1.6:
            # "HEY JULIE - HEY JULIE" : repeat, second one a hair higher and quieter
            pieces += [w, np.zeros(int(SR * 0.06)), fade(varispeed(w, 1.06), 4, 30) * db(-2.0)]
        elif mi == len(mids) - 1:
            on = last_word_onset(x, (s, e))
            if on:
                a = int(on * SR); b = int(e * SR)
                head = x[int(s * SR):a]
                pieces.append(slash_cut(head, np.zeros(0)))
                pieces.append(stutter(x[a:b], n=int(rng.integers(2, 4))))
            else:
                pieces.append(w)
        else:
            pieces.append(w)
        cursor = e
    pieces.append(x[int(cursor * SR):])
    y = np.concatenate(pieces)
    return y, segments(y)


def punctuate(x, segs, extra=0.3):
    """Widen the biggest middle pause so the punctuation rev has room to land before the next line."""
    if len(segs) < 3:
        return x, segs
    gaps = [(s1 - e0, gi) for gi, ((s0, e0), (s1, e1)) in enumerate(zip(segs[:-1], segs[1:])) if gi > 0]
    if not gaps:
        return x, segs
    gi = max(gaps)[1]
    cut = int((segs[gi][1] + 0.05) * SR)
    y = np.concatenate([x[:cut], np.zeros(int(SR * extra)), x[cut:]])
    segs2 = segs[:gi + 1] + [(a + extra, b + extra) for a, b in segs[gi + 1:]]
    return y, segs2


def glitch_finale(x, segs, tapestop=True, stutter_on=True, rise=False, rise_semis=4.5, slap_word=False, intro_end=None):
    """Pitch-rise (way up), dramatic slapback and/or stutter on the last word of the intro phrase;
    tape-stop the very last word of the clip. Returns (audio, segments, intro_end)."""
    y = x
    if (stutter_on or rise or slap_word) and segs:
        s, e = segs[0]
        on = last_word_onset(y, (s, e))
        if on:
            a = int(on * SR); b = int(e * SR)
            w = y[a:b]
            if rise:
                w = riser(w, semis=rise_semis)
            if stutter_on:
                w = stutter(w, n=3)
            y = np.concatenate([y[:a], w, y[b:]])
            if intro_end:
                intro_end += (len(w) - (b - a)) / SR
            segs = merge_intro(segments(y), intro_end)  # measured BEFORE the echo tail bridges the pause
            if slap_word:
                y = word_slap(y, a, a + len(w))
    if tapestop and segs:
        s, e = segs[-1]
        on = last_word_onset(y, (s, e)) or (s + 0.6 * (e - s))
        a = int(on * SR); b = int(e * SR)
        y = np.concatenate([y[:a], tape_stop(y[a:b]), y[b:]])
        segs = segs[:-1] + [(s, min(e, len(y) / SR))]
    return y, segs, intro_end


# ----------------------------------------------------------------------------- voice fx
def voice_fx(x, pitch_st=-2.0, sub_db=-10.0, drive_db=6.0):
    ratio = 2 ** (pitch_st / 12)
    main = ff(x, f"rubberband=pitch={ratio:.5f}:tempo=1.0:pitchq=quality") if abs(pitch_st) > 0.05 else x
    sub = ff(x, "rubberband=pitch=0.5:tempo=1.0,lowpass=f=200:p=2") * db(sub_db)
    n = min(len(main), len(sub)); v = main[:n] + sub[:n]
    chain = ("highpass=f=70,"
             "equalizer=f=120:t=q:w=1.0:g=4,equalizer=f=250:t=q:w=1.2:g=2,"
             "equalizer=f=900:t=q:w=1.3:g=-2.5,equalizer=f=2800:t=q:w=1.0:g=3,"
             "highshelf=f=8000:g=-2,"
             f"volume={drive_db:.1f}dB,asoftclip=type=tanh:threshold=0.72:output=0.9,"
             "acompressor=threshold=-18dB:ratio=4:attack=5:release=80:makeup=4,"
             "alimiter=limit=0.95:attack=2:release=30:level=false")
    return ff(v, chain)


def arena_ir(rt60_low=2.2, rt60_mid=1.7, rt60_high=0.9, pre_ms=28):
    n = int(SR * (pre_ms / 1000 + rt60_low * 1.1)); t = np.arange(n) / SR
    noise = RNG.standard_normal(n)
    bands = []
    for lo, hi, rt in ((20, 250, rt60_low), (250, 2500, rt60_mid), (2500, 12000, rt60_high)):
        sos = butter(2, [lo, hi], btype="band", fs=SR, output="sos")
        bands.append(sosfilt(sos, noise) * np.exp(-6.91 * t / rt))
    tail = sum(bands)
    ir = np.zeros(n)
    pre = int(SR * pre_ms / 1000)
    ir[pre:] += tail[:n - pre] * 0.25
    for d_ms, g in ((21, 0.55), (37, 0.45), (53, 0.38), (79, 0.3), (101, 0.24), (140, 0.18)):  # early reflections
        i = pre + int(SR * d_ms / 1000)
        if i < n:
            ir[i:i + 40] += g * np.hanning(40) * RNG.standard_normal(40) * 0.5 + g * (np.arange(40) == 0)
    return ir / (np.sqrt(np.sum(ir ** 2)) + 1e-9)


def reverb(x, wet_db=-13.0):
    ir = arena_ir()
    wet = fftconvolve(x, ir)[:len(x) + len(ir)]
    wet = ff(wet, "lowpass=f=6500")
    out = np.zeros(len(wet)); out[:len(x)] += x; out += wet * db(wet_db)
    return out


def slapback(x, delay_ms=125, fb=0.32, taps=3, level_db=-9.0):
    d = int(SR * delay_ms / 1000); out = np.zeros(len(x) + d * taps)
    y = ff(x, "lowpass=f=3200,highpass=f=300")
    for k in range(1, taps + 1):
        out[k * d:k * d + len(y)] += y * (fb ** (k - 1)) * db(level_db)
    out[:len(x)] += x
    return out


# ----------------------------------------------------------------------------- beds & hits
def asset(name):
    return load(os.path.join(ASSETS, name))


def bed(name, length, target_rms_db, fade_in=0.15, fade_out=1.2):
    a = asset(name); reps = int(np.ceil(length / len(a))) + 1
    y = np.tile(a, reps)[:length]
    y *= db(target_rms_db - rms_db(y))
    fi = int(SR * fade_in); fo = int(SR * fade_out)
    y[:fi] *= np.linspace(0, 1, fi); y[-fo:] *= np.linspace(1, 0, fo) ** 2
    return y


def duck(y, voice_env, depth_db):
    g = db(-depth_db * voice_env[:len(y)]) if len(voice_env) >= len(y) else np.concatenate([db(-depth_db * voice_env), np.ones(len(y) - len(voice_env))])
    return y * g


def place(mix, clip, at_s, gain_db, pan=0.0, target_peak_db=-1.0):
    """Drop a clip into a stereo (2, n) mix. pan -1..1, or "sweep" to fly it left -> right."""
    c = clip * db(target_peak_db - peak_db(clip)) * db(gain_db)
    i = max(0, int(at_s * SR)); j = min(mix.shape[1], i + len(c)); c = c[:j - i]
    if isinstance(pan, str):
        th = (np.linspace(-0.9, 0.9, len(c)) + 1) * np.pi / 4
    else:
        th = (pan + 1) * np.pi / 4
    mix[0, i:j] += c * np.cos(th); mix[1, i:j] += c * np.sin(th)


_REV_CACHE = {}


def rev_variants():
    """Seven different engine sounds carved out of the one V8 sample + the engine bed, so no two revs match."""
    if _REV_CACHE:
        return _REV_CACHE
    r = asset("v8_rev.wav"); r *= db(-1.0 - peak_db(r))
    eb = asset("engine_bed.wav")
    v = {
        "rev_full": r,
        "rev_blip": fade(r[:int(SR * 1.1)], 5, 250),
        "rev_high": varispeed(r, 1.22),                                   # smaller, angrier engine
        "rev_low": varispeed(r, 0.8),                                     # big block
        "rev_reverse": fade(r[:int(SR * 1.6)][::-1], 300, 5),             # swell INTO a word
        "rev_double": np.concatenate([fade(r[:int(SR * 0.42)], 5, 60), np.zeros(int(SR * 0.09)), fade(r[:int(SR * 0.55)], 5, 200)]),
        "rev_hold": fade(eb[int(SR * 4.0):int(SR * 5.9)] * db(-1.0 - peak_db(eb)), 120, 500),  # rev-up-and-hold
    }
    _REV_CACHE.update(v)
    return v


def schedule_hits(segs, total_s, seed=11, siren="siren_wail.wav"):
    """(sound, time, gain_db, pan) from the pause structure.
    No crash sounds. Pyro only where a sentence ends (intro phrase + finale). Regular revs rotate through
    variants on about half the small gaps; ONE extreme rev punctuates the end of the middle line.
    One siren sweeps across the intro phrase."""
    rng = np.random.default_rng(seed)
    order = ["rev_high", "rev_double", "rev_low", "rev_blip", "rev_hold", "rev_full"]
    rng.shuffle(order)
    revs = iter(order * 3)
    extremes = ["rev_extreme_a.wav", "rev_extreme_c.wav", "rev_extreme_b.wav"]
    rng.shuffle(extremes)
    side = [-0.55, 0.55]; k = 0
    first = segs[0][0] if segs else 0.45
    hits = [("rev_reverse", max(0.0, first - 1.55), -4.0, 0.0)]           # swell into the first word
    if siren:
        hits.append((siren, first + 0.15, -11.0, "sweep"))                 # doppler siren under the intro phrase
    gaps = [(s1 - e0, gi, e0) for gi, ((s0, e0), (s1, e1)) in enumerate(zip(segs[:-1], segs[1:]))]
    middle = [g for g in gaps if g[1] > 0]
    big = max(middle, key=lambda g: g[0])[1] if middle else None
    for gap, gi, e0 in gaps:
        at = max(0.0, e0 - 0.04); pan = side[k % 2]; k += 1
        if gi == 0:                                                        # end of the intro phrase: the blast
            hits += [("pyro_explosion.wav", at, -4.0, 0.0), (next(revs), at + 0.25, -7.0, pan)]
        elif gi == big and gap >= 0.25:                                    # end of the middle line: THE extreme rev
            hits.append(("rev_extreme_a.wav", e0 + 0.06, 0.0, 0.0))        # full level, dead center, right after the word
        elif gap >= 0.14 and rng.random() < 0.5:
            hits.append((next(revs), at, -8.0 + float(rng.uniform(-2, 2)), pan))
    end = segs[-1][1] if segs else total_s
    # finale: pyro + the dragster launch with the screaming tires (Kevin: "hilarious, bring that back")
    hits += [("pyro_explosion.wav", max(0.0, end - 0.05), -3.0, 0.0), ("rev_extreme_b.wav", end + 0.02, -1.0, 0.25)]
    return hits


def hit_sound(name):
    return rev_variants()[name] if (name.startswith("rev_") and not name.endswith(".wav")) else asset(name)


# ----------------------------------------------------------------------------- main
def render(take_path, out_path, cadence=False, stutter_on=False, slash=False, tapestop=False,
           pitch=-2.0, sub_db=-10.0, engine_db=-17.0, riff_db=-16.0, crowd_db=-26.0, lufs=-9.0,
           wet_db=-13.0, slap_db=-9.0, seed=3, vari=False, rise=False, riff="riff_speedy_a.wav", siren="siren_wail.wav",
           glitch_mid=False, rise_semis=4.5, slap_word=False, punct=False, intro_end=None, report=None):
    raw = load(take_path)
    raw *= db(-3.0 - peak_db(raw))
    segs = merge_intro(segments(raw), intro_end)  # TTS timestamps (when known) say where the intro line ends
    v = raw
    if cadence:
        v, segs = cadence_middle(v, segs, seed=seed, stutter_on=stutter_on, slash_on=slash, vari=vari, rise=rise)
        segs = merge_intro(segs, intro_end)
    if glitch_mid:
        v, segs = glitch_middle(v, segs, seed=seed)
        segs = merge_intro(segs, intro_end)
    if punct:
        v, segs = punctuate(v, segs)
    if stutter_on or tapestop or rise or slap_word:
        v, segs, intro_end = glitch_finale(v, segs, tapestop=tapestop, stutter_on=stutter_on, rise=rise,
                                           rise_semis=rise_semis, slap_word=slap_word, intro_end=intro_end)
    v = voice_fx(v, pitch_st=pitch, sub_db=sub_db)
    v = slapback(v, level_db=slap_db)
    v = reverb(v, wet_db=wet_db)
    v *= db(-10.0 - rms_db(v[:int(segs[-1][1] * SR)] if segs else v))  # voice sits at -10 dBFS RMS pre-master
    pre = 0.45                                        # engine lead-in before the first word
    voice_end = pre + (segs[-1][1] if segs else len(v) / SR)
    total = int(SR * (voice_end + 2.0))
    mix = np.zeros((2, total))
    p0 = int(SR * pre); n = min(len(v), total - p0); mix[:, p0:p0 + n] += v[:n]
    env = env_follow(mix[0]); env = np.clip(env / (np.percentile(env, 97) + 1e-9), 0, 1)
    fade_start = voice_end + 0.5
    beds = np.zeros((2, total))
    for name, level, depth, pan in (("engine_bed.wav", engine_db, 5.0, 0.0), (riff, riff_db, 6.0, -0.35),
                                    ("crowd_bed.wav", crowd_db, 4.0, 0.35)):
        b = bed(name, total, level, fade_in=0.12, fade_out=0.01)
        i = int(SR * fade_start); j = min(total, i + int(SR * 1.3))
        b[i:j] *= np.linspace(1, 0, j - i) ** 2; b[j:] = 0
        b = duck(b, env, depth); th = (pan + 1) * np.pi / 4
        beds[0] += b * np.cos(th) * 1.414; beds[1] += b * np.sin(th) * 1.414
    segs_p = [(a + pre, b_ + pre) for a, b_ in segs]
    hits = schedule_hits(segs_p, voice_end, seed=seed + 11, siren=siren)
    for name, at, g, pan in hits:
        if name == "rev_extreme_a.wav":  # beds dip 7 dB under the punctuation rev so it stands alone
            i = int(SR * at); j = min(total, i + int(SR * 1.4)); n = j - i
            dip = np.ones(n); a_ = int(SR * 0.02); r_ = int(SR * 0.5)
            dip[:a_] = np.linspace(1, db(-7), a_); dip[a_:n - r_] = db(-7); dip[n - r_:] = np.linspace(db(-7), 1, r_)
            beds[:, i:j] *= dip
    mix += beds
    for name, at, g, pan in hits:
        place(mix, hit_sound(name), at, g, pan)
    mix = np.tanh(mix * 1.15) / np.tanh(1.15)  # glue / soft clip
    tmp = out_path + ".pre.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-i", "pipe:0", tmp],
                   input=mix.T.astype(np.float32).tobytes(), check=True)
    # two-pass loudnorm so the integrated loudness actually lands on target
    p1 = subprocess.run(["ffmpeg", "-v", "info", "-i", tmp, "-af", f"loudnorm=I={lufs}:TP=-1.0:LRA=9:print_format=json",
                         "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(p1.stderr[p1.stderr.rfind("{"):p1.stderr.rfind("}") + 1])
    ln = (f"loudnorm=I={lufs}:TP=-1.0:LRA=9:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp, "-af", ln + ",alimiter=limit=0.94:attack=2:release=40",
                    "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "192k", out_path], check=True)
    os.remove(tmp)
    info = {"take": take_path, "out": out_path, "voice_s": round(len(v) / SR, 2), "total_s": round(total / SR, 2),
            "segments": [(round(a, 2), round(b, 2)) for a, b in segs_p],
            "hits": [(h[0], round(h[1], 2), h[2], str(h[3])) for h in hits],
            "cadence": cadence, "stutter": stutter_on, "slash": slash, "tapestop": tapestop, "vari": vari, "rise": rise,
            "rise_semis": rise_semis, "glitch_mid": glitch_mid, "slap_word": slap_word, "punct": punct, "intro_end": intro_end, "riff": riff, "riff_db": riff_db, "pitch": pitch}
    if report is not None:
        report.append(info)
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("take"); ap.add_argument("out")
    ap.add_argument("--cadence", action="store_true"); ap.add_argument("--stutter", action="store_true")
    ap.add_argument("--slash", action="store_true"); ap.add_argument("--tapestop", action="store_true")
    ap.add_argument("--pitch", type=float, default=-2.0); ap.add_argument("--sub", type=float, default=-10.0)
    ap.add_argument("--engine", type=float, default=-17.0); ap.add_argument("--riff", type=float, default=-16.0)
    ap.add_argument("--crowd", type=float, default=-26.0); ap.add_argument("--lufs", type=float, default=-9.0)
    ap.add_argument("--wet", type=float, default=-13.0); ap.add_argument("--slap", type=float, default=-9.0)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--vari", action="store_true", help="tape-style varispeed cadence (pitch moves with speed)")
    ap.add_argument("--rise", action="store_true", help="pitch risers on accent words")
    ap.add_argument("--riffname", default="riff_speedy_a.wav"); ap.add_argument("--siren", default="siren_wail.wav")
    ap.add_argument("--glitchmid", action="store_true"); ap.add_argument("--risesemis", type=float, default=4.5)
    ap.add_argument("--slapword", action="store_true"); ap.add_argument("--punct", action="store_true")
    a = ap.parse_args()
    print(json.dumps(render(a.take, a.out, a.cadence, a.stutter, a.slash, a.tapestop, a.pitch, a.sub,
                            a.engine, a.riff, a.crowd, a.lufs, a.wet, a.slap, a.seed, a.vari, a.rise, a.riffname, a.siren or None,
                            a.glitchmid, a.risesemis, a.slapword, a.punct), indent=1))
