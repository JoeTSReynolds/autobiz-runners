# sensitive.py: one table, caption / spoken forms. Run: python3 test_sensitive.py (prints ok)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trending import sensitive as S

CASES = [  # original, caption, spoken
    ("rape", "r*pe", "grape"), ("raped", "r*ped", "graped"), ("raping", "r*ping", "graping"), ("rapes", "r*pes", "grapes"),
    ("rapist", "r*pist", "grapist"), ("rapists", "r*pists", "grapists"),
    ("sexual assault", "s*xual assault", "S.A."), ("sexually assaulted", "s*xually assaulted", "S.A.'d"),
    ("murder", "m*rder", "unalive"), ("murdered", "m*rdered", "unalived"), ("murderer", "m*rderer", "unaliver"),
    ("killed", "k*lled", "unalived"), ("killing", "k*lling", "unaliving"), ("kill", "k*ll", "unalive"),
    ("suicide", "s*icide", "self-unalive"), ("pedophile", "p*dophile", "PDF file"), ("paedophiles", "p*dophiles", "PDF files"),
    ("sex", "s*x", "six"), ("sexual", "s*xual", "sixual"), ("sexually", "s*xually", "sixually"),
    ("porn", "p*rn", "corn"), ("pornography", "p*rnography", "corn"), ("child abuse", "child ab*se", "child A.B."),
]
for o, c, s in CASES:
    assert S.caption_text(o) == c, (o, S.caption_text(o))
    assert S.spoken_text(o) == s, (o, S.spoken_text(o))
# case of the original is kept
assert S.caption_text("Rape") == "R*pe" and S.caption_text("RAPE") == "R*PE" and S.caption_text("He was Raped.") == "He was R*ped."
assert S.spoken_text("Rape") == "Grape" and S.spoken_text("SEXUAL ASSAULT") == "S.A."
# multi-word, whitespace, sentence full stop after "S.A."
assert S.caption_text("a sexual  assault case") == "a s*xual assault case"
assert S.spoken_text("He survived a sexual assault. Then") == "He survived a S.A. Then"
assert S.caption_text("It was a sexual assault.") == "It was a s*xual assault."
# punctuation survives; one token
assert S.caption_word("rape,") == "r*pe," and S.caption_word('"Rapist!"') == '"R*pist!"' and S.caption_word("hello") == "hello"
# spoken forms are NOT mapped back: a genuine "six" or "grape" is never censored
assert S.caption_text("Six women") == "Six women" and S.caption_text("grape juice") == "grape juice" and S.caption_word("Grapist.") == "Grapist."
assert S.caption_text("unalived") == "unalived" and S.caption_text("a PDF file") == "a PDF file" and S.spoken_text("popcorn skill") == "popcorn skill"
# sex rows: case, punctuation, word boundaries
assert S.caption_text("Sex, SEXUAL and sexually.") == "S*x, S*XUAL and s*xually." and S.spoken_text("Sex sells.") == "Six sells."
assert S.caption_word("sex!") == "s*x!"
for w in ["Sussex", "Essex", "sextet", "Sexton", "sexy"]:
    assert S.caption_text(w) == w and S.spoken_text(w) == w, w
# spoken_map: spoken string plus captions for substituted tokens only, by (token, occurrence)
assert S.spoken_map("Six women alleged sex.") == ("Six women alleged six.", {("six", 1): "s*x"})
assert S.spoken_map("Sex, then six, then sex!") == ("Six, then six, then six!", {("six", 0): "S*x", ("six", 2): "s*x"})
assert S.spoken_map("nothing here") == ("nothing here", {})
assert S.spoken_map("a pedophile ring")[1] == {("pdf", 0): "p*dophile", ("file", 0): ""}
assert S.spoken_map("He was raped.")[1] == {("graped", 0): "r*ped"}
assert S.spoken_map("[sex scene] He had sex.") == ("[sex scene] He had six.", {("six", 0): "s*x"})
assert S.spoken_map("a sexual assault.")[1] == {("s.a", 0): "s*xual assault"}
# v3 tags pass through, even when they hold a term
assert S.spoken_text("[dramatic] He raped her. [pause] [murder scene]") == "[dramatic] He graped her. [pause] [murder scene]"
assert S.caption_text("[whispers] rape") == "[whispers] r*pe"
# ordinary words that contain the letters are untouched
for w in ["drape", "grapefruit", "scrapes", "therapist", "skill", "skilled", "skills", "popcorn", "murderous"]:
    assert S.caption_text(w) == w, w
# idempotent
assert S.caption_text(S.caption_text("Rape and murder")) == "R*pe and m*rder"
print("ok")
