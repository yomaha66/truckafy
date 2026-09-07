"""Word-accurate edit stage for the TRUCK-A-FY mixer.

The ElevenLabs take comes back with character timestamps, so every edit here lands on a WORD, not on a
silence-detector guess:

  * take normalisation — v3 at stability 0 is wildly variable take to take (median pitch swings by 8
    semitones, pace by 40 %); pace is pulled toward the signed-off reference with pitch-preserving tempo,
    over-long screamed words are capped, dead air between sentences is set to what the effects need;
  * the intro's accent word gets the octave riser (+ slapback, applied by the caller);
  * ONE doubled phrase ("HEY JULIE - HEY JULIE"), never a word that just came out of the intro triple;
  * stutter / slash cuts on accent words, budgeted and spaced so it reads as attitude, not a broken file;
  * tape-stop on the last word;
  * hits (pyro, revs, siren, licks) are scheduled from the words' output times.

Nothing here changes a word; it changes timing and delivery only.
"""
import re

import numpy as np

import mix

SR = mix.SR
TARGET_F0 = 150.0          # Hz, pyin median (16 kHz, 55-320 Hz) of the take the recipe was signed off on (rex_t1_baseline)
TARGET_RATE = 11.0         # letters per second over the ordinary words of a take at the signed-off pace
PITCH_BASE = -2.0          # the signed-off pitch shift for a take that already sits at TARGET_F0


class Word:
    __slots__ = ("text", "t0", "t1", "sent", "intro", "accent", "last", "o0", "o1", "after_break")

    def __init__(self, text, t0, t1):
        self.text, self.t0, self.t1 = text, t0, t1
        self.sent = 0; self.intro = False; self.accent = False; self.last = False
        self.after_break = False  # follows an audio tag / ' ... ' pause (or is the first word)
        self.o0 = self.o1 = None  # output-time span, filled by assemble()

    @property
    def clean(self):
        return re.sub(r"[^A-Za-z0-9']", "", self.text)

    def __repr__(self):
        return f"{self.text}@{self.t0:.2f}-{self.t1:.2f}"


# ----------------------------------------------------------------------------- parsing
def words_from_alignment(alignment, intro_line=""):
    """Words with times; audio tags and ' ... ' pause tokens are dropped. Sentence 0 is the intro line
    (if any), the last word of every sentence is its accent word."""
    chars = alignment["characters"]
    st = alignment["character_start_times_seconds"]
    en = alignment["character_end_times_seconds"]
    out, cur, t0, prev = [], "", None, 0.0
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                out.append(Word(cur, t0, prev)); cur, t0 = "", None
        else:
            if t0 is None:
                t0 = s
            cur += c; prev = e
    if cur:
        out.append(Word(cur, t0, prev))
    ws, brk = [], True
    for w in out:
        if (w.text.startswith("[") and w.text.endswith("]")) or w.text.strip(".") == "":
            brk = True
            continue
        w.after_break = brk; brk = False
        ws.append(w)
    n_intro = len(intro_line.split()) if intro_line else 0
    sent = 0 if n_intro else 1
    for i, w in enumerate(ws):
        w.intro = i < n_intro
        w.sent = sent
        ends = (i == n_intro - 1) or (not w.intro and re.search(r"[.!?]['\"]?$", w.text) is not None) or i == len(ws) - 1
        if ends:
            w.last = w.accent = True
            sent += 1
    return ws


def refine_words(ws, x, thr_db=-32.0, min_gap=0.14):
    """ElevenLabs' character times are only roughly right, in two specific ways: a tag's own span eats the
    first half second of the word after it, and words that run together can come back 0.08 s long while the
    audio shows 0.8 s. The alignment is kept where it agrees with the envelope; a word after a break starts
    where its speech island starts, and any run of words containing a squashed one is re-split across its
    span in proportion to letters (snapped to envelope valleys)."""
    isl = mix.segments(x, thr_db=thr_db, min_gap=min_gap, min_len=0.06)
    if not isl or not ws:
        return ws
    def owner(t):
        for k, (a, b) in enumerate(isl):
            if a - 0.02 <= t <= b + 0.02:
                return k
        return None
    # 1. onsets after breaks: the island the word lives in starts the word
    for i, w in enumerate(ws):
        if not w.after_break:
            continue
        k = owner(0.5 * (w.t0 + w.t1)) or owner(w.t1)
        if k is None:
            continue
        a = isl[k][0]
        prev_end = ws[i - 1].t1 if i else -1.0
        if a > prev_end and a < w.t0:
            w.t0 = a
    # 2. squashed words: re-split the run of words sharing their speech island
    def squashed(w):
        return (w.t1 - w.t0) < max(0.06, 0.045 * len(w.clean))
    own = []
    for w in ws:
        k = owner(0.5 * (w.t0 + w.t1))
        if k is None:
            m = 0.5 * (w.t0 + w.t1)
            k = min(range(len(isl)), key=lambda k: min(abs(isl[k][0] - m), abs(isl[k][1] - m)))
        own.append(k)
    done = set()
    for i, w in enumerate(ws):
        if not squashed(w) or i in done:
            continue
        lo = i - 1 if i > 0 and own[i - 1] == own[i] and ws[i - 1].sent == w.sent else i
        hi = i + 1 if i + 1 < len(ws) and own[i + 1] == own[i] and ws[i + 1].sent == w.sent else i
        run = ws[lo:hi + 1]
        a, b = run[0].t0, run[-1].t1
        ia, ib = isl[own[i]]
        if hi + 1 >= len(ws) or own[hi + 1] != own[i]:
            b = max(b, ib)
        if len(run) == 1 or b - a < 0.12:
            for v in run:
                v.t1 = max(v.t1, v.t0 + 0.05)
            if len(run) == 1:
                run[0].t1 = max(run[0].t1, min(b, run[0].t0 + 0.6))
        else:
            weights = [max(1, len(v.clean)) for v in run]; tot = float(sum(weights))
            vals = mix.valleys(x, a, b)
            cuts, acc = [a], 0.0
            for wgt in weights[:-1]:
                acc += wgt
                t = a + (b - a) * acc / tot
                near = [v for v in vals if abs(v - t) <= 0.08 and v > cuts[-1] + 0.05]
                if near:
                    t = min(near, key=lambda v: abs(v - t))
                cuts.append(max(cuts[-1] + 0.05, min(t, b - 0.05)))
            cuts.append(b)
            for v, t0, t1 in zip(run, cuts[:-1], cuts[1:]):
                v.t0, v.t1 = t0, t1
        done.update(range(lo, hi + 1))
    return ws


def sentences(ws):
    out = {}
    for w in ws:
        out.setdefault(w.sent, []).append(w)
    return [out[k] for k in sorted(out)]


# ----------------------------------------------------------------------------- measurements
def letters_per_second(ws):
    """Pace of the ordinary words (the screamed accent words are long by design and measured separately)."""
    plain = [w for w in ws if not w.accent] or ws
    spoken = sum(w.t1 - w.t0 for w in plain)
    letters = sum(len(w.clean) for w in plain)
    return letters / spoken if spoken > 0.3 else TARGET_RATE


def median_f0(x, sr=SR):
    """Median fundamental of the voiced frames (librosa pyin on a 16 kHz copy; ~0.7 s for a 10 s take).
    Returns TARGET_F0 when nothing is voiced or librosa is missing."""
    try:
        import warnings
        import librosa
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            y = librosa.resample(x.astype(np.float32), orig_sr=sr, target_sr=16000)
            f0, _, _ = librosa.pyin(y, fmin=55, fmax=320, sr=16000, frame_length=1024, hop_length=256)
        v = f0[~np.isnan(f0)]
        return float(np.median(v)) if len(v) >= 8 else TARGET_F0
    except ImportError:
        return TARGET_F0


def normalise_plan(ws, x, human=True):
    """Global tempo factor (>1 = faster) and the pitch shift to use, from the take's own numbers.
    human=True keeps the voice a voice: no pitch shift unless the take is unusually bright (then a gentle drop),
    at most 8 % tempo, and the numbers are reported so the caller can re-roll a take that is out of range
    instead of bending it into an angry robot."""
    rate = letters_per_second(ws)
    f0 = median_f0(x)
    if human:
        tempo = float(np.clip(TARGET_RATE / rate, 1.0, 1.08))
        pitch = float(np.clip(12 * np.log2(160.0 / f0), -1.5, 0.0)) if f0 > 160.0 else 0.0
    else:
        tempo = float(np.clip(TARGET_RATE / rate, 1.0, 1.25))
        pitch = float(np.clip(PITCH_BASE + 12 * np.log2(TARGET_F0 / f0), -3.0, 3.0))
    ok = (f0 >= 100.0) and (rate >= 8.5)
    return dict(rate=round(rate, 2), tempo=round(tempo, 3), f0=round(f0, 1), pitch=round(pitch, 2), ok=ok)


def take_score(alignment, x, intro_line=""):
    """Quick quality number for a raw take (higher = closer to the signed-off delivery), for re-roll decisions."""
    ws = refine_words(words_from_alignment(alignment, intro_line), x)
    if len(ws) < 2:
        return 0.0, {}
    n = normalise_plan(ws, x)
    pace = min(1.0, n["rate"] / TARGET_RATE)
    pitch = 1.0 - min(1.0, abs(np.log2(max(n["f0"], 1.0) / 135.0)) * 1.5)
    return round(0.5 * pace + 0.5 * pitch, 3), n


# ----------------------------------------------------------------------------- the plan
def plan_effects(ws, seed=3, human=True, plan=None):
    """Decide which words get which effect. Returns a dict keyed by word index.
    plan="n" is the signed-off N set placed on words: intro riser+slapback, the opening phrase of the message
    doubled when it is short enough, slash cut + stutter on the accent word of the line before the last one,
    tape-stop on the last word. plan="human" budgets ONE glitch in the body instead."""
    if plan == "n":
        return plan_effects_n(ws, seed)
    if human:
        return plan_effects_human(ws, seed)
    rng = np.random.default_rng(seed)
    sents = sentences(ws)
    body = [s for s in sents if not s[0].intro]
    fx = {}
    idx = {id(w): i for i, w in enumerate(ws)}
    intro_word = ws[0].clean.lower() if ws and ws[0].intro else None
    # intro accent: riser (+ slapback, applied by the caller)
    if ws and ws[0].intro:
        fx[idx[id(sents[0][-1])]] = {"riser": True, "slap": True}
    if not body:
        return fx
    last_glitch_t = -9.0
    # ONE doubled phrase at the top of the first body sentence
    first = body[0]
    if len(first) >= 4:
        start = 1 if (intro_word and first[0].clean.lower() == intro_word) else 0
        phrase = []
        for w in first[start:-1]:
            phrase.append(w)
            if sum(v.t1 - v.t0 for v in phrase) >= 0.55 or len(phrase) == 3:
                break
        dur = sum(v.t1 - v.t0 for v in phrase)
        if 0.3 <= dur <= 1.4 and first[-1].t0 - phrase[-1].t1 >= 0.9 and len(first) >= 5:
            fx[idx[id(phrase[0])]] = {"double_from": idx[id(phrase[0])], "double_to": idx[id(phrase[-1])]}
            last_glitch_t = phrase[-1].t1
    # accent words of the body sentences before the final one: alternate stutter / slash, spaced out
    styles = ["stutter", "slash", "stutter+slash"]
    rng.shuffle(styles)
    k = 0
    for s in body[:-1]:
        w = s[-1]
        if w.t0 - last_glitch_t < 1.0:
            continue
        style = "stutter+slash" if s is body[-2] and len(body) >= 2 else styles[k % len(styles)]
        k += 1
        fx.setdefault(idx[id(w)], {}).update({"stutter": "stutter" in style, "slash": "slash" in style})
        last_glitch_t = w.t1
    # the very last word: tape-stop (+ a slash cut in front of it half the time when the sentence is long)
    final = body[-1]
    w = final[-1]
    d = fx.setdefault(idx[id(w)], {})
    d["tapestop"] = True
    if len(final) >= 4 and rng.random() < 0.5 and w.t0 - last_glitch_t >= 1.0:
        d["slash"] = True
    if len(body) == 1 and len(final) >= 3 and rng.random() < 0.6:
        d["stutter"] = True
    return fx


def plan_effects_n(ws, seed=3):
    rng = np.random.default_rng(seed)
    sents = sentences(ws)
    body = [s for s in sents if not s[0].intro]
    fx = {}
    idx = {id(w): i for i, w in enumerate(ws)}
    intro_word = ws[0].clean.lower() if ws and ws[0].intro else None
    if ws and ws[0].intro:
        fx[idx[id(sents[0][-1])]] = {"riser": True, "slap": True}
    if not body:
        return fx
    first = body[0]
    if len(first) >= 4 and len(body) >= 2:
        start = 1 if (intro_word and first[0].clean.lower() == intro_word) else 0
        phrase = []
        for w in first[start:-1]:
            phrase.append(w)
            if sum(v.t1 - v.t0 for v in phrase) >= 0.55 or len(phrase) == 3:
                break
        dur = sum(v.t1 - v.t0 for v in phrase)
        if 0.3 <= dur <= 1.4 and first[-1].t0 - phrase[-1].t1 >= 0.9:
            fx[idx[id(phrase[0])]] = {"double_from": idx[id(phrase[0])], "double_to": idx[id(phrase[-1])]}
    if len(body) >= 2:
        w = body[-2][-1]
        fx.setdefault(idx[id(w)], {}).update({"stutter": True, "slash": True})
    w = body[-1][-1]
    fx.setdefault(idx[id(w)], {})["tapestop"] = True
    return fx


def plan_effects_human(ws, seed=3):
    rng = np.random.default_rng(seed)
    sents = sentences(ws)
    body = [s for s in sents if not s[0].intro]
    fx = {}
    idx = {id(w): i for i, w in enumerate(ws)}
    intro_word = ws[0].clean.lower() if ws and ws[0].intro else None
    if ws and ws[0].intro:
        fx[idx[id(sents[0][-1])]] = {"riser": True, "slap": True}
    if not body:
        return fx
    options = []
    first = body[0]
    if len(first) >= 5:
        start = 1 if (intro_word and first[0].clean.lower() == intro_word) else 0
        phrase = []
        for w in first[start:-1]:
            phrase.append(w)
            if sum(v.t1 - v.t0 for v in phrase) >= 0.55 or len(phrase) == 3:
                break
        dur = sum(v.t1 - v.t0 for v in phrase)
        if 0.3 <= dur <= 1.4 and first[-1].t0 - phrase[-1].t1 >= 0.9:
            options.append(("double", phrase))
    if len(body) >= 2:
        options.append(("stutter", body[-2][-1]))
        options.append(("slash", body[-2][-1]))
    if options and (len(body) >= 2 or rng.random() < 0.5):
        weights = np.array([{"double": 0.45, "stutter": 0.35, "slash": 0.2}[k] for k, _ in options])
        kind, target = options[int(rng.choice(len(options), p=weights / weights.sum()))]
        if kind == "double":
            fx[idx[id(target[0])]] = {"double_from": idx[id(target[0])], "double_to": idx[id(target[-1])]}
        else:
            fx.setdefault(idx[id(target)], {})[kind] = True
    w = body[-1][-1]
    fx.setdefault(idx[id(w)], {})["tapestop"] = True
    return fx


def gap_after(ws, i):
    """Desired output gap (s) after word i, or None to keep the take's own (short) gap."""
    if i >= len(ws) - 1:
        return None
    w, nxt = ws[i], ws[i + 1]
    if nxt.sent != w.sent:
        body = [s for s in sentences(ws) if not s[0].intro]
        if w.intro:
            return 0.5                    # pyro + rev fill this
        if body and nxt.sent == body[-1][0].sent and len(body) >= 2:
            return 0.85                   # the punctuation rev needs room before the last line
        return 0.45
    return None                           # inside a sentence: keep the take's own gap, trimmed to 0.26 s


# ----------------------------------------------------------------------------- assembly
def _slice(x, a, b):
    return x[max(0, int(a * SR)):max(0, int(b * SR))]


def gap_piece(x, e, b, nb, want, max_keep=0.26, drop_db=35.0, exact=True):
    """Audio for the gap [b, nb] between two words. The longest silent run inside it is shortened to
    `want` (or padded up to it, when a sentence boundary needs room for a hit); speech tails on either
    side are kept as they are. want=None means 'keep at most max_keep of silence' (max_keep=None: keep
    it all). exact=False makes `want` a minimum only: the take's own pause survives when it is longer."""
    if nb <= b:
        return np.zeros(int(SR * (want or 0.0)))
    fa, fb = int(b / (0.01)), int(nb / 0.01)
    if fb - fa < 3:
        seg = _slice(x, b, nb)
        return np.concatenate([seg, np.zeros(int(SR * max(0.0, (want or 0.0) - (nb - b))))])
    thr = max(e[max(0, fa - 30):fa].max() if fa > 0 else -60, e[fb:fb + 30].max() if fb + 30 <= len(e) else -60) - drop_db
    quiet = e[fa:fb] < thr
    # longest quiet run
    best, run, start = (0, fa, fa), 0, fa
    for k, q in enumerate(quiet, start=fa):
        if q:
            if run == 0:
                start = k
            run += 1
            if run > best[0]:
                best = (run, start, k + 1)
        else:
            run = 0
    n_run, s0, s1 = best
    if n_run < 3:                                   # no real silence: keep the gap as it is (+ pad if a hit needs room)
        seg = _slice(x, b, nb)
        pad = max(0.0, (want or 0.0) - (nb - b))
        return np.concatenate([seg, np.zeros(int(SR * pad))])
    t0, t1 = s0 * 0.01, s1 * 0.01
    if want is not None:
        keep = min(t1 - t0, want) if exact else min(t1 - t0, max(want, max_keep or 9.0))
    else:
        keep = min(t1 - t0, max_keep) if max_keep is not None else (t1 - t0)
    pad = max(0.0, (want - (t1 - t0))) if want is not None else 0.0
    head = mix.fade(_slice(x, b, t0 + keep), 0, 10) if (t0 + keep) > b else np.zeros(0)
    tailp = mix.fade(_slice(x, t1, nb), 10, 0) if nb > t1 else np.zeros(0)
    return np.concatenate([head, np.zeros(int(SR * pad)), tailp])


def assemble(x, ws, fx, tempo=1.0, cap_accent=1.05, cap_intro=1.6, cap_final=1.25, cap_word=0.8, seed=3, trim=True):
    """Apply the global tempo, then rebuild the take word by word with the planned effects and gaps.
    Sets each word's output span (o0, o1). Returns (audio, intro_accent_span or None).
    trim=False keeps the announcer's own timing: no pause is shortened (structural pauses are only padded up
    to what a hit needs, and capped at 1.1 s) and no word is compressed unless it runs past 2.2 s."""
    rng = np.random.default_rng(seed + 1)
    if not trim:
        cap_accent = cap_intro = cap_final = cap_word = 2.2
    if abs(tempo - 1.0) > 0.02:
        x = mix.ff(x, f"rubberband=tempo={tempo:.3f}:pitch=1.0:pitchq=quality:transients=crisp")
        for w in ws:
            w.t0 /= tempo; w.t1 /= tempo
    e = mix.frame_db(x)
    lead = 0.012; tail = 0.03
    # anything the announcer does AFTER the last word (a laugh from a [laughs] tag) is kept, and the last word
    # is then left alone instead of tape-stopped
    tail_end = None
    if ws:
        after = ws[-1].t1 + 0.05
        trail = mix.segments(x[int(after * SR):], thr_db=-34, min_gap=0.2, min_len=0.25) if len(x) > after * SR else []
        if trail:
            tail_end = min(len(x) / SR, after + trail[-1][1] + 0.12)
            fx.get(len(ws) - 1, {}).pop("tapestop", None)
    pieces = []
    pos = 0.0          # output seconds so far
    intro_span = None
    i = 0
    n = len(ws)
    # room tone before the first word (trimmed to 0.25 s)
    h0 = max(0.0, ws[0].t0 - lead - 0.25) if n else 0.0
    head = mix.fade(_slice(x, h0, ws[0].t0 - lead), 10, 2) if n and ws[0].t0 - lead > h0 else np.zeros(0)
    pieces.append(head); pos += len(head) / SR
    while i < n:
        w = ws[i]
        f = fx.get(i, {})
        a, b = max(0.0, w.t0 - lead), w.t1 + tail
        # the source gap before this word is the room tone we may reuse
        chunk = _slice(x, a, b)
        # caps on over-long screamed words
        limit = cap_intro if w.intro and w.accent else cap_final if (i == n - 1) else cap_accent if w.accent else cap_word
        if (b - a) > limit + 0.05:
            chunk = mix.tempo(chunk, (b - a) / limit)
        if "double_from" in f:
            j = f["double_to"]
            phrase = _slice(x, a, ws[j].t1 + tail)
            rep = mix.fade(mix.varispeed(phrase, 1.06), 4, 30) * mix.db(-2.0)
            gapz = np.zeros(int(SR * 0.06))
            out = np.concatenate([phrase, gapz, rep])
            # output spans for the doubled words: first pass only
            t = pos
            for k in range(i, j + 1):
                d = (ws[k].t1 + tail) - (max(0.0, ws[k].t0 - lead))
                ws[k].o0 = t; ws[k].o1 = t + d; t += d
            pieces.append(out); pos += len(out) / SR
            i = j + 1
            if i < n:
                g = gap_piece(x, e, ws[j].t1 + tail, ws[i].t0 - lead, gap_after(ws, j),
                              max_keep=(0.26 if trim else 1.1), exact=trim)
                pieces.append(g); pos += len(g) / SR
            continue
        if f.get("slash") and pieces:
            prev = pieces.pop()
            cut = mix.slash_cut(prev, np.zeros(0))
            pieces.append(cut)
            pos += (len(cut) - len(prev)) / SR
        if f.get("riser"):
            chunk = mix.riser(chunk, semis=10.0)
        if f.get("stutter"):
            chunk = mix.stutter(chunk, n=int(rng.integers(2, 4)))
        if f.get("tapestop"):
            chunk = mix.tape_stop(chunk)
        w.o0 = pos; w.o1 = pos + len(chunk) / SR
        if f.get("slap"):
            intro_span = (w.o0, w.o1)
        pieces.append(chunk); pos = w.o1
        # gap to the next word: only SILENCE is trimmed or padded, never the tail of a word
        if i < n - 1:
            g = gap_piece(x, e, b, ws[i + 1].t0 - lead, gap_after(ws, i), max_keep=(0.26 if trim else 1.1), exact=trim)
            pieces.append(g); pos += len(g) / SR
        i += 1
    if tail_end and ws:
        extra = mix.fade(_slice(x, ws[-1].t1 + tail, tail_end), 2, 60)
        pieces.append(extra)
        ws[-1].o1 = pos + len(extra) / SR
    y = np.concatenate([p for p in pieces if len(p)])
    return y, intro_span


# ----------------------------------------------------------------------------- hits
def schedule_hits(ws, pre, seed=11, siren="siren_wail.wav", licks=True):
    """(sound, time, gain_db, pan) from word output times (+ pre-roll)."""
    rng = np.random.default_rng(seed)
    order = ["rev_high", "rev_double", "rev_low", "rev_blip", "rev_hold", "rev_full"]
    rng.shuffle(order); revs = iter(order * 4)
    lick_names = ["lick_dive.wav", "lick_shred.wav", "lick_squeal.wav", "lick_stab.wav"]
    rng.shuffle(lick_names); lick_iter = iter(lick_names * 2)
    sents = sentences(ws)
    body = [s for s in sents if not s[0].intro]
    first = ws[0].o0 + pre
    hits = [("rev_reverse", max(0.0, first - 1.55), -4.0, 0.0)]
    if ws[0].intro and siren:
        hits.append((siren, first + 0.15, -11.0, "sweep"))
    side = [-0.55, 0.55]; k = 0
    if ws[0].intro:
        e = sents[0][-1].o1 + pre
        hits += [("pyro_explosion.wav", e - 0.04, -4.0, 0.0)]
        if len(body) >= 2:
            hits.append((next(revs), e + 0.21, -7.0, side[k % 2])); k += 1
        else:
            hits.append(("rev_extreme_a.wav", e + 0.1, 0.0, 0.0))      # only one body line: the big rev goes here
        if licks:
            hits.append((next(lick_iter), e + 0.12, -11.0, 0.5))          # a lick answers the intro, off to the right
    for si, s in enumerate(body[:-1]):
        e = s[-1].o1 + pre
        if si == len(body) - 2:
            hits.append(("rev_extreme_a.wav", e + 0.06, 0.0, 0.0))      # THE punctuation rev
        elif rng.random() < 0.6:
            hits.append((next(revs), e - 0.04, -8.0 + float(rng.uniform(-2, 2)), side[k % 2])); k += 1
    end = ws[-1].o1 + pre
    hits += [("pyro_explosion.wav", max(0.0, end - 0.05), -3.0, 0.0), ("rev_extreme_b.wav", end + 0.02, -1.0, 0.25)]
    if licks:
        hits.append((next(lick_iter), end + 0.5, -7.0, -0.4))             # solo out over the tires
    return hits
