"""TRUCK-A-FY script builder: any typed message -> the performance script ElevenLabs v3 reads.

The user's words are never changed, removed, or reordered. What we add is delivery:
  * an INTRO line before the message — either an arena catchphrase from the pool, or the user's own
    first word said three times ("Hey! Hey! HEEEY!") the way "Sunday! Sunday! SUUUNDAY!" works —
    the third one gets its vowel stretched so the octave riser + slapback in mix.py land on it;
  * the last word of every sentence in CAPS with a stretched vowel (the announcer leans on it);
  * ElevenLabs audio tags and " ... " pauses that the mixer's pause-detection keys off.

    build("can you grab dog food on the way home")
    -> "[shouts] Can! Can! CAAAN! ... [shouts] can you grab dog food on the way HOOOME! ..."
"""
import random
import re

INTROS = [
    "Sunday, Sunday, SUUUNDAY!",
    "Saturday night, Saturday night, SATURDAAAY NIGHT!",
    "This Sunday, at the DOOOME!",
    "One night only, ONE NIGHT OOONLY!",
    "Be there, be there, BE THEEERE!",
    "We'll sell you the whole seat, but you'll only need the EEEDGE!",
    "Kids seats are still five BUUUCKS!",
    "Side by side racing, car crushing, and the fire breathing JET CAAAR!",
    "Monster trucks, monster trucks, MONSTER TRUUUCKS!",
    "Live, live, LIIIVE!",
]

VOWELS = "aeiouAEIOU"
_WORD = re.compile(r"[^\W\d_][\w'\-]*")


def stretch(word, n=3):
    """HOME -> HOOOME: repeat the first vowel so the announcer leans on it."""
    for i, ch in enumerate(word):
        if ch in VOWELS:
            return word[:i] + ch * n + word[i + 1:]
    return word


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def accent_last_word(sentence):
    """Uppercase + stretch the final word; force an exclamation mark (punctuation, not words)."""
    m = re.match(r"^(.*?)([A-Za-z0-9][A-Za-z0-9'\-]*)([^A-Za-z0-9]*)$", sentence, flags=re.S)
    if not m:
        return sentence
    head, last, tail = m.groups()
    last = last.upper()
    if len(last) > 2 and not last.isdigit():
        last = stretch(last)
    tail = re.sub(r"[.!?]+$", "", tail)  # drop the sentence-final mark; we end on "!"
    return f"{head}{last}{tail}!"


def triple(word):
    """Sunday! Sunday! SUUUNDAY! — the third repeat is the one the riser and slapback hit."""
    w = word.strip("'-")
    cap = w[0].upper() + w[1:] if w else w
    return f"{cap}, {cap}, {stretch(cap.upper())}!"


def first_word(text):
    m = _WORD.match(text.lstrip())
    return m.group(0) if m else None


def build(text, intro="auto", seed=None, with_intro=False):
    """intro: 'auto' (random mix of the two), 'first' (user's first word x3), 'arena' (pool), 'none'.
    with_intro=True also returns the intro line so the caller can locate its end in the TTS timestamps."""
    rng = random.Random(seed)
    text = re.sub(r"\s+", " ", text.strip())
    fw = first_word(text)
    if intro == "auto":
        intro = rng.choice(["first", "first", "arena"]) if fw else "arena"
    if intro == "first" and not fw:
        intro = "arena"
    if intro == "first":
        intro_line = triple(fw)
    elif intro == "arena":
        intro_line = rng.choice(INTROS)
    else:
        intro_line = ""
    body = []
    for i, s in enumerate(sentences(text)):
        tag = "[excited][shouts]" if i % 2 == 0 else "[shouts]"
        body.append(f"{tag} {accent_last_word(s)}")
    parts = ([f"[shouts] {intro_line}"] if intro_line else []) + body
    perf = " ... ".join(parts)
    return (perf, intro_line) if with_intro else perf


if __name__ == "__main__":
    import sys
    msg = " ".join(sys.argv[1:]) or "Hey Julie, can you grab dog food for Jasper on the way home? We are almost out."
    for mode in ("first", "arena", "none"):
        print(f"[{mode}] {build(msg, intro=mode, seed=1)}")
