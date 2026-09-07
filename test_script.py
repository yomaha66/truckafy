"""Offline tests for script.py's verbatim guarantee. No API calls.

    ./.venv/Scripts/python.exe test_script.py

The hard rule (CLAUDE.md, HANDOFF.md section 1): the user's words are read verbatim. Repeating the
user's own first word is allowed, and stretching its vowel is allowed; emitting a word they never
typed is not. The intro is the only place that has ever broken this.
"""
import re
import sys

import script

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  -- " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def unstretch(word):
    """CAAAF -> CAF: undo stretch() so an intro word can be compared to what the user typed."""
    return re.sub(r"([aeiou])\1{2,}", r"\1", word, flags=re.I)


def intro_of(text, seed=1):
    return script.build(text, intro="first", seed=seed).split(" ... ")[0]


def words(s):
    return [w for w in re.findall(r"[^\W\d_][\w'\-]*", s)]


# --- first_word returns the user's actual first word, not an ASCII slice of it ---
for text, want in [("Café closes at five", "Café"),
                   ("Únete al club", "Únete"),
                   ("can you grab dog food", "can"),
                   ("5 minutes till dinner", None)]:
    got = script.first_word(text)
    check(f"first_word({text!r})", got == want, f"got {got!r}, wanted {want!r}")

# --- the invariant that matters: an intro only ever says words the user typed ---
for text in ["Café closes at five", "Únete al club", "5 minutes till dinner",
             "can you grab dog food on the way home", "¿Dónde está la fiesta?"]:
    intro = intro_of(text)
    typed = {w.lower() for w in words(text)}
    spoken = {unstretch(w).lower() for w in words(intro.replace("[shouts]", ""))}
    is_arena = any(intro == "[shouts] " + i for i in script.INTROS)
    check(f"intro says only typed words: {text!r}",
          is_arena or spoken <= typed,
          f"intro {intro!r} added {sorted(spoken - typed)}")

# --- the body is untouched no matter what ---
for text in ["Café closes at five", "Únete al club"]:
    body = script.build(text, intro="none", seed=1)
    check(f"body keeps every typed word: {text!r}",
          all(w in body for w in text.split()[:-1]),
          f"body was {body!r}")

print()
if fails:
    print(f"{len(fails)} FAILED: {', '.join(fails)}")
    sys.exit(1)
print("all passed")
