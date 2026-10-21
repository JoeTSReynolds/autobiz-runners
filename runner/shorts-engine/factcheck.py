#!/usr/bin/env python3
"""Mechanical fact gates (no model calls): quotes must appear in the source text,
and every number a storyboard says or shows must trace to a fact.
Run: python3 factcheck.py <brief.json> <sources-dir> [<storyboard.json>]   (exit 1 on any failure)
"""
import json, os, re, sys

MIN_QUOTE = 25
_T = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                    "–": "-", "—": "-", " ": " "})


def norm(s):
    return re.sub(r"\s+", " ", s.lower().translate(_T)).strip()


def check_quotes(brief, sources_dir):
    kept, errors, cache = [], [], {}
    for f in brief.get("facts", []):
        q = norm(f.get("quote", "")).rstrip(" .,;:!?\"'…")
        path = os.path.join(sources_dir, f"{f.get('source')}.txt")
        if len(q) < MIN_QUOTE:
            err = "quote too short to verify"
        elif not os.path.exists(path):
            err = f"source {f.get('source')} has no text file"
        else:
            if path not in cache:
                cache[path] = norm(open(path, encoding="utf-8").read())
            err = None if q in cache[path] else "quote not found in source text"
        if err:
            errors.append(f"fact {f.get('id')}: {err}")
        else:
            kept.append(f)
    return kept, errors



def check_quote_parts(storyboard, source_text):
    words = lambda t: " ".join(re.findall(r"[\w']+", norm(t)))
    src, errors = words(source_text), []
    for sc in storyboard.get("scenes", []):
        for p in sc.get("parts", []):
            if p.get("blueprint") == "quote":
                q = " ".join(l.get("text", "") for l in p.get("params", {}).get("lines", []))
                if f" {words(q)} " not in f" {src} ":
                    errors.append(f'scene {sc.get("id")}: quote "{q}" is not in the source text; quote the source word for word or use a statement')
    return errors

ONES = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
ORD = "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split()
TENS = "thirty forty fifty sixty seventy eighty ninety".split()
WORDS = {w: i + 1 for i, w in enumerate(ONES)}
WORDS.update({w: i + 1 for i, w in enumerate(ORD)})
WORDS.update({w: 30 + 10 * i for i, w in enumerate(TENS)})
WORDS.update({w[:-2] + "ieth": 30 + 10 * i for i, w in enumerate(TENS)})  # thirtieth...
WORDS.update(hundred=100, hundredth=100, thousand=1000, thousandth=1000, million=1e6, millionth=1e6,
             billion=1e9, billionth=1e9, half=2, halves=2, quarter=4, quarters=4)
NUM = re.compile(r"(\d+)\s*/\s*(\d+)|\$?(\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)%?")


def numbers(text):
    """[(value, as_written)] for digits, with fractions as numerator + denominator."""
    out = []
    for m in NUM.finditer(text):
        if m.group(1):
            out += [(float(m.group(1)), m.group(1)), (float(m.group(2)), m.group(2))]
        else:
            out.append((float(m.group(3).replace(",", "")), m.group(0)))
    return out


def fact_numbers(text):
    t = text.lower()
    vals = {v for v, _ in numbers(t)}
    vals |= {WORDS[w] for w in re.findall(r"[a-z]+", t) if w in WORDS}
    for m in re.finditer(r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[- ](one|two|three|four|five|six|seven|eight|nine)\b", t):
        vals.add(WORDS[m.group(1)] + WORDS[m.group(2)])
    return vals


def traces(v, fvals):
    return any(abs(v - f) <= 0.01 * abs(f) or abs(v - f / 1000) <= 0.01 * abs(f / 1000)
               or abs(v - f / 1e6) <= 0.01 * abs(f / 1e6) for f in fvals)


def strings(o, key=""):
    """Yield string values, skipping image/at/*At keys and {x, y} points."""
    if key in ("image", "at") or key.endswith("At"):
        return
    if isinstance(o, str):
        yield o
    elif isinstance(o, list):
        for x in o:
            yield from strings(x, key)
    elif isinstance(o, dict):
        if "x" in o and "y" in o:
            return
        for k, x in o.items():
            yield from strings(x, k)


def check_numbers(storyboard, facts):
    fvals = set()
    for f in facts:
        fvals |= fact_numbers(f.get("text", ""))
    errors = []
    for sc in storyboard.get("scenes", []):
        texts = [re.sub(r"\[[^\]]*\]", " ", sc.get("say", ""))]
        for p in sc.get("parts", []):
            texts += strings(p.get("params", {}))
        seen = set()
        for t in texts:
            for v, w in numbers(t):
                if (v == int(v) and 0 <= v <= 3) or w in seen:
                    continue
                if not traces(v, fvals):
                    seen.add(w)
                    errors.append(f'scene {sc.get("id")}: "{w}" is not in any fact')
    return errors


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    brief = json.load(open(sys.argv[1]))
    kept, errs = check_quotes(brief, sys.argv[2])
    if len(sys.argv) > 3:
        errs += check_numbers(json.load(open(sys.argv[3])), kept)
    print(f"{len(kept)}/{len(brief.get('facts', []))} facts have verified quotes")
    for e in errs:
        print("FAIL", e)
    sys.exit(1 if errs else 0)
