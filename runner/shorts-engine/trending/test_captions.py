# captions.chunks (one grouping for every renderer), the swear list, and each renderer's subtitle times. Run: python3 test_captions.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trending import captions as C
from trending.formats import topn, tribute, casefile

W = lambda w, s, e, **k: {"w": w, "s": s, "e": e, **k}

# pause split: 1.2 s between two words -> two groups, even though both fit one
g = C.chunks([W("Hello", 0, .4), W("there", 1.6, 2.0)], 3, 16)
assert [x["text"] for x in g] == ["Hello", "there"], g
assert len(C.chunks([W("Hello", 0, .4), W("there", .5, 1.0)], 3, 16)) == 1

# end timing: last word end + hold, never past the next start, never stretched over a silence; min_dur unless the next starts sooner
g = C.chunks([W("One.", 0, .5), W("Two.", .6, .7), W("Three.", 5, 5.5)], 3, 16)
assert g[0]["end"] == .6, g            # next starts at .6
assert abs(g[1]["end"] - 1.1) < 1e-9, g  # .7 + hold .4, not 5.0
assert abs(g[2]["end"] - 5.9) < 1e-9, g
g = C.chunks([W("Hi.", 0, .1), W("Yo", 2, 2.5)], 3, 16)
assert abs(g[0]["end"] - .5) < 1e-9, g  # .1 + hold
g = C.chunks([W("Hi.", 0, .1), W("Yo", .2, 2.5)], 3, 16, hold=0)
assert g[0]["end"] == .2, g  # min_dur never pushes past the next start

# punctuation: . ? ! always; , ; : only once the group has 2+ words
g = C.chunks([W("Well,", 0, .2), W("yes", .2, .4), W("really,", .4, .6), W("so", .6, .8)], 9, 99)
assert [x["text"] for x in g] == ["Well, yes really,", "so"], g
assert [x["text"] for x in C.chunks([W("No.", 0, .2), W("Yes", .2, .4)], 9, 99)] == ["No.", "Yes"]

# cleaning, cap and censoring
g = C.chunks([W(">>", 0, .1), W("[laughs]", .1, .2), W(">>Piss", .2, .5), W("off", .5, .8, cap="of"), W("x", .8, 1, cap="")], 9, 99)
assert [x["text"] for x in g] == ["P*ss of"], g
assert [w["w"] for w in g[0]["words"]] == ["P*ss", "of"], g
assert C.chunks([W("Six", 0, .2, cap="s*x")], 3, 16)[0]["text"] == "s*x"
assert C.chunks([W("sex", 0, .2)], 3, 16)[0]["text"] == "s*x"

# max words / chars
assert [x["text"] for x in C.chunks([W(w, i * .2, i * .2 + .2) for i, w in enumerate("a b c d e".split())], 3, 99)] == ["a b c", "d e"]
assert [x["text"] for x in C.chunks([W("abcdefgh", 0, .2), W("ijklmnop", .2, .4)], 9, 16)] == ["abcdefgh", "ijklmnop"]

# swear list: stems anywhere, masking keeps case and punctuation; false friends are untouched
for w, m in [("fuck", "f*ck"), ("Shit,", "Sh*t,"), ("BITCH!", "B*TCH!"), ("cunt", "c*nt"), ("asshole", "assh*le"), ("arse", "ars*"), ("ass", "a*s"),
             ("arsehead", "ars*head"), ("bastard", "b*stard"), ("dick", "d*ck"), ("piss", "p*ss"), ("bollocks", "b*llocks"), ("wanker", "w*nker"),
             ("twat", "tw*t"), ("prick", "pr*ck"), ("cock", "c*ck"), ("slut", "sl*t"), ("whore", "wh*re"), ("bullshit", "bullsh*t"),
             ("motherfucker", "motherf*cker"), ("dipshit", "dipsh*t"), ("fucking", "f*cking")]:
    assert C.censor(w) == m, (w, C.censor(w), m)
assert "*" in C.censor("jackass") and "*" in C.censor("dumbass")
for w in ["class", "pass", "glass", "assume", "cocktail", "Dickens", "scrap", "Scunthorpe", "bass", "assist", "peacock", "Hitchcock", "swank", "Essex",
          "assassin", "classic", "harass", "passage", "cockpit", "shiny", "pistol", "Mississippi"]:
    assert C.censor(w) == w, (w, C.censor(w))

# renderers: no caption on screen during a 1.5 s pause between two words
def shown(spans, t):
    return [s for s in spans if s[0] <= t < s[1]]

ws = [W("Is", 41.0, 41.2), W("there", 41.2, 41.5), W("a", 43.0, 43.1), W("chance", 43.1, 43.5)]
sp = [(a, b) for _, a, b in topn._chunks(ws, 41.0, 45.0, 0.0)]
assert len(sp) == 2 and not any(shown(sp, t) for t in (1.1, 1.5, 1.9)) and shown(sp, 0.1) and shown(sp, 2.2), sp

sp = [(c["start"], c["end"]) for c in tribute._chunks(ws)]
assert len(sp) == 2 and not any(shown(sp, t) for t in (42.0, 42.5, 42.9)), sp

cap = casefile.Captions([[W("Is", 0, .2), W("there", .2, .5), W("a", 2.0, 2.1), W("chance", 2.1, 2.5)]])
assert len(cap.show) == 2 and not any(shown(cap.show, t) for t in (1.0, 1.5, 1.9)) and shown(cap.show, .1), cap.show
# fillers and stutter repeats never reach a caption; "but" alone, "like", "so" and "you know" are words
g = C.chunks([W("So", 0, .2), W("um", .2, .4), W("but", .4, .6), W("but", .6, .8), W("I", .8, .9), W("I", .9, 1.0), W("like", 1.0, 1.2),
              W("Uhh,", 1.2, 1.4), W("the", 1.4, 1.5), W("the", 1.5, 1.6), W("you", 1.6, 1.7), W("know", 1.7, 1.9), W("Hmm", 1.9, 2.1), W("erm", 2.1, 2.2), W("mm", 2.2, 2.3)], 99, 99)
assert [x["text"] for x in g] == ["So but I like the you know"], g
assert [x["text"] for x in C.chunks([W("But", 0, .2), W("no.", .2, .5), W("No.", .6, .9)], 99, 99)] == ["But no.", "No."]  # a sentence end is not a stutter
assert C.filler_idx(["a", "um", "no,", "no,", "b", "b"]) == {1, 4}
print("ok")
