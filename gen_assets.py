"""Procedurally synthesize the TRUCK-A-FY sound bed and pyro SFX.

Runs once at container build time (see Dockerfile). Everything is generated
from oscillators + noise so the repo stays text-only and license-free.
Output: 44.1 kHz 16-bit mono WAVs in ./assets
"""
import os
import wave
import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(OUT, exist_ok=True)


def save(name, sig):
    sig = np.clip(sig, -1.0, 1.0)
    pcm = (sig * 32767).astype(np.int16)
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote", name, f"{len(sig)/SR:.2f}s")


def t(seconds):
    return np.arange(int(SR * seconds)) / SR


def env(n, a, d, s, r, hold=0.0):
    """ADSR envelope, times in seconds, n samples."""
    a, d, r, hold = (int(x * SR) for x in (a, d, r, hold))
    sus = max(n - a - d - r - hold, 0)
    parts = [
        np.linspace(0, 1, a, endpoint=False),
        np.ones(hold),
        np.linspace(1, s, d, endpoint=False),
        np.full(sus, s),
        np.linspace(s, 0, r),
    ]
    e = np.concatenate(parts)
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def saw(freq, tt):
    return 2 * ((freq * tt) % 1.0) - 1


def square(freq, tt):
    return np.sign(np.sin(2 * np.pi * freq * tt))


def distort(x, drive=8.0):
    return np.tanh(x * drive) / np.tanh(drive)


def lowpass(x, cutoff):
    """One-pole lowpass (cheap, good enough for grit)."""
    rc = 1.0 / (2 * np.pi * cutoff)
    alpha = (1.0 / SR) / (rc + 1.0 / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


# ---------------------------------------------------------------- metal riff
def heavy_metal_loop():
    """120 BPM palm-muted thrash riff, 4 bars (8 s), E-standard power chords."""
    bpm = 120
    beat = 60 / bpm
    eighth = beat / 2
    # riff in 8ths: (midi note or None for rest/mute). E1=40
    E, G, A, Bb = 40, 43, 45, 46
    bar1 = [E, E, E, G, E, E, A, E]
    bar2 = [E, E, E, G, E, E, Bb, A]
    riff = bar1 + bar2 + bar1 + [E, E, G, A, Bb, A, G, E]
    out = np.zeros(int(SR * eighth * len(riff)))
    for i, note in enumerate(riff):
        f = 440 * 2 ** ((note - 69) / 12)
        n = int(SR * eighth)
        tt = t(eighth)[:n]
        # power chord: root + fifth + octave, slightly detuned pair for width
        chord = (
            saw(f, tt) + saw(f * 1.004, tt) * 0.8
            + saw(f * 1.5, tt) * 0.7 + saw(f * 2.0, tt) * 0.5
        )
        chug = env(n, 0.003, 0.09, 0.35, 0.03)  # palm-mute shape
        sig = distort(chord * chug, 12.0)
        start = i * n
        out[start:start + n] += sig
    # kick + snare under it
    for i in range(len(riff)):
        pos = int(i * SR * eighth)
        if i % 2 == 0:  # kick on the beat
            n = int(SR * 0.12)
            tt = t(0.12)[:n]
            kick = np.sin(2 * np.pi * (60 + 120 * np.exp(-tt * 40)) * tt) * env(n, 0.001, 0.1, 0, 0.02)
            out[pos:pos + n] += kick * 0.9
        if i % 4 == 2:  # snare on 2 and 4
            n = int(SR * 0.15)
            snare = np.random.uniform(-1, 1, n) * env(n, 0.001, 0.12, 0, 0.03)
            out[pos:pos + n] += snare * 0.5
    out = lowpass(out, 6000)
    out = distort(out, 2.5)
    return out / np.max(np.abs(out)) * 0.9


# ---------------------------------------------------------------- pyro
def pyro_explosion():
    """Stadium pyro: sub thump + noise blast with a lowpass sweep, 1.6 s."""
    n = int(SR * 1.6)
    tt = t(1.6)[:n]
    thump = np.sin(2 * np.pi * (45 + 200 * np.exp(-tt * 25)) * tt) * env(n, 0.001, 0.35, 0.1, 0.5)
    noise = np.random.uniform(-1, 1, n)
    blast = noise * env(n, 0.002, 0.25, 0.25, 1.0)
    # crude sweep: mix lowpassed + raw with time-varying weight
    lp = lowpass(noise, 600) * env(n, 0.05, 0.6, 0.4, 0.9)
    sig = thump * 1.2 + blast * 0.7 + lp * 2.5
    sig = distort(sig, 3.0)
    return sig / np.max(np.abs(sig)) * 0.95


# ---------------------------------------------------------------- glass
def glass_shatter():
    """Bright noise crackle bursts, 0.9 s."""
    n = int(SR * 0.9)
    sig = np.zeros(n)
    rng = np.random.default_rng(7)
    for _ in range(40):
        pos = int(rng.uniform(0, 0.5) * SR)
        ln = int(rng.uniform(0.01, 0.06) * SR)
        f = rng.uniform(3000, 9000)
        tt = np.arange(ln) / SR
        shard = np.sin(2 * np.pi * f * tt) * np.random.uniform(-1, 1, ln) * env(ln, 0.001, 0.02, 0.2, 0.02)
        end = min(pos + ln, n)
        sig[pos:end] += shard[: end - pos]
    sig += np.random.uniform(-1, 1, n) * env(n, 0.001, 0.15, 0.05, 0.5) * 0.4
    return sig / np.max(np.abs(sig)) * 0.8


# ---------------------------------------------------------------- airhorn
def stadium_airhorn():
    """Detuned square-wave chord, 1.2 s. The classic 'BWAAAMP'."""
    n = int(SR * 1.2)
    tt = t(1.2)[:n]
    freqs = [233.0, 277.2, 311.1, 349.2]  # Bb3 major-ish cluster, dissonant on purpose
    sig = sum(square(f * (1 + 0.006 * k), tt) for k, f in enumerate(freqs))
    sig = lowpass(sig, 2500) * env(n, 0.03, 0.1, 0.9, 0.35)
    sig = distort(sig, 3.0)
    return sig / np.max(np.abs(sig)) * 0.85


# ---------------------------------------------------------------- engine
def v8_rev():
    """V8 rev: sawtooth with rising fundamental and firing-pulse modulation, 1.4 s."""
    n = int(SR * 1.4)
    tt = t(1.4)[:n]
    f0 = 35 + 90 * (1 - np.exp(-tt * 3.5))  # rpm climb
    phase = np.cumsum(f0) / SR
    sig = 2 * (phase % 1.0) - 1
    pulses = (np.sin(2 * np.pi * phase * 4) > 0.6).astype(float)  # 8 cyl / 2 = 4 fires per rev
    sig = distort(sig * (0.6 + 0.4 * pulses), 6.0)
    sig = lowpass(sig, 1800) * env(n, 0.02, 0.1, 0.9, 0.5)
    sig += np.random.uniform(-1, 1, n) * 0.08 * env(n, 0.02, 0.1, 0.9, 0.5)
    return sig / np.max(np.abs(sig)) * 0.9


if __name__ == "__main__":
    np.random.seed(1990)
    save("heavy_metal_loop.wav", heavy_metal_loop())
    save("pyro_explosion.wav", pyro_explosion())
    save("glass_shatter.wav", glass_shatter())
    save("stadium_airhorn.wav", stadium_airhorn())
    save("v8_rev.wav", v8_rev())
