"""Demonetisation-safe wording: one table, three forms of each sensitive term.

    original   what the script says          rape
    caption    on screen, titles, metadata   r*pe   (capitalisation of the original kept: Rape -> R*pe, RAPE -> R*PE)
    spoken     what the voice says           grape

caption_text(s)  originals -> caption form. Spoken forms are NOT mapped back, so a genuine "six" or "grape" is never censored.
spoken_text(s)   originals -> spoken forms, for TTS input; ElevenLabs v3 tags like [dramatic] pass through untouched.
spoken_map(s)    (spoken string, {(token, occurrence): caption core}) for the tokens a substitution produced; tts.narrate uses it
                 with cap_words so narration captions are censored only where the script said the word.
caption_word(w)  one caption token; leading and trailing punctuation stay.

Not covered: words printed inside article screenshots, and real people saying the word in source clips.
"""
import re

# The owner may change any "spoken" (or "caption") form below. `original` is a case-insensitive regex matched as a whole word.
TERMS = [
    {"pattern": "rape", "caption": "r*pe", "spoken": "grape"},
    {"pattern": "raped", "caption": "r*ped", "spoken": "graped"},
    {"pattern": "raping", "caption": "r*ping", "spoken": "graping"},
    {"pattern": "rapes", "caption": "r*pes", "spoken": "grapes"},
    {"pattern": "rapist", "caption": "r*pist", "spoken": "grapist"},
    {"pattern": "rapists", "caption": "r*pists", "spoken": "grapists"},
    {"pattern": "sex", "caption": "s*x", "spoken": "six"},
    {"pattern": "sexual", "caption": "s*xual", "spoken": "sixual"},
    {"pattern": "sexually", "caption": "s*xually", "spoken": "sixually"},
    {"pattern": "sexual assault", "caption": "s*xual assault", "spoken": "S.A."},
    {"pattern": "sexually assaulted", "caption": "s*xually assaulted", "spoken": "S.A.'d"},
    {"pattern": "murder", "caption": "m*rder", "spoken": "unalive"},
    {"pattern": "murders", "caption": "m*rders", "spoken": "unalives"},
    {"pattern": "murdered", "caption": "m*rdered", "spoken": "unalived"},
    {"pattern": "murdering", "caption": "m*rdering", "spoken": "unaliving"},
    {"pattern": "murderer", "caption": "m*rderer", "spoken": "unaliver"},
    {"pattern": "murderers", "caption": "m*rderers", "spoken": "unalivers"},
    {"pattern": "kill", "caption": "k*ll", "spoken": "unalive"},
    {"pattern": "kills", "caption": "k*lls", "spoken": "unalives"},
    {"pattern": "killed", "caption": "k*lled", "spoken": "unalived"},
    {"pattern": "killing", "caption": "k*lling", "spoken": "unaliving"},
    {"pattern": "suicide", "caption": "s*icide", "spoken": "self-unalive"},
    {"pattern": "pa?edophile", "caption": "p*dophile", "spoken": "PDF file"},
    {"pattern": "pa?edophiles", "caption": "p*dophiles", "spoken": "PDF files"},
    {"pattern": "pa?edophilia", "caption": "p*dophilia", "spoken": "PDF file"},
    {"pattern": "porn", "caption": "p*rn", "spoken": "corn"},
    {"pattern": "pornography", "caption": "p*rnography", "spoken": "corn"},
    {"pattern": "child abuse", "caption": "child ab*se", "spoken": "child A.B."},
]

_TAG = re.compile(r"(\[[^\]]*\])")


def _ws(s):
    return re.escape(s).replace("\\ ", r"\s+")


def _build(pairs):
    """[(regex, form, canon)] -> (compiled alternation, [(form, canon)]). canon is how the matched text is normally written.
    First pair wins a duplicate regex; longer regexes are tried first."""
    seen, ps = set(), []
    for p, f, c in pairs:
        if p.lower() not in seen:
            seen.add(p.lower())
            ps.append((p, (f, c)))
    ps.sort(key=lambda x: -len(x[0]))
    rx = re.compile(r"(?<!\w)(?:" + "|".join(f"(?P<g{i}>{p})" for i, (p, _) in enumerate(ps)) + r")(?!\w)", re.I)
    return rx, [f for _, f in ps]


_TO_SPOKEN = _build([(t["pattern"].replace(" ", r"\s+"), t["spoken"], "") for t in TERMS])
_TO_CAPTION = _build([(t["pattern"].replace(" ", r"\s+"), t["caption"], "") for t in TERMS])


def _shape(s):
    letters = [c for c in s if c.isalpha()]
    return "upper" if len(letters) > 1 and s.upper() == s else "cap" if s[:1].isupper() else "lower"


def _case(src, form, canon):
    """Carry the matched text's capitalisation onto the form, unless it is just the canonical spelling (PDF file, S.A.)."""
    k = _shape(src)
    if k == _shape(canon):
        return form
    return form.upper() if k == "upper" else form[0].upper() + form[1:] if k == "cap" else form


def _pieces(text, table):
    """Yield (text, matched_original_or_None); tags and untouched text come through with None."""
    rx, forms = table
    for i, p in enumerate(_TAG.split(text)):
        if i % 2:
            yield p, None
            continue
        pos = 0
        for m in rx.finditer(p):
            f = _case(m.group(), *forms[int(m.lastgroup[1:])])
            if f.endswith(".") and p[m.end():m.end() + 1] == ".":  # "S.A." + sentence full stop
                f = f[:-1]
            yield p[pos:m.start()], None
            yield f, m.group()
            pos = m.end()
        yield p[pos:], None


def _sub(text, table):
    return "".join(t for t, _ in _pieces(text, table))


_EDGE = ".,!?;:\"“”'’…—"  # the punctuation tts strips from word times
_TOK = re.compile(r"\[[^\]]*\]|\S+")


def _norm(w):
    return w.strip(_EDGE).lower()


def caption_text(s):
    return _sub(s, _TO_CAPTION)


def spoken_text(s):
    return _sub(s, _TO_SPOKEN)


def spoken_map(s):
    out, subs, n = [], [], 0
    for t, o in _pieces(s, _TO_SPOKEN):
        if o:
            subs.append((n, n + len(t), caption_text(o)))
        out.append(t)
        n += len(t)
    sp, caps, seen, used = "".join(out), {}, {}, set()
    for m in _TOK.finditer(sp):
        k = "" if m.group().startswith("[") else _norm(m.group())
        if not k:
            continue
        c = seen[k] = seen.get(k, -1) + 1
        for j, (a, b, cap) in enumerate(subs):
            if m.start() < b and m.end() > a:  # first token of a substitution carries the caption form, the rest are dropped
                caps[(k, c)] = "" if j in used else cap
                used.add(j)
                break
    return sp, caps


def cap_words(words, caps):
    """Give each word of one sentence a `cap`: its caption form where (token, occurrence) is in caps, else itself. Punctuation kept."""
    seen = {}
    for w in words:
        k = _norm(w["w"])
        c = seen[k] = seen.get(k, -1) + 1
        core = caps.get((k, c))
        if core is None:
            w["cap"] = w["w"]
        else:
            t = w["w"].lstrip(_EDGE)
            w["cap"] = w["w"][:len(w["w"]) - len(t)] + core + w["w"][len(w["w"].rstrip(_EDGE)):] if core else ""
    return words


def caption_word(w):
    return caption_text(w)
