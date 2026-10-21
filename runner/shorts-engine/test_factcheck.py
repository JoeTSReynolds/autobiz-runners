#!/usr/bin/env python3
"""Tests for factcheck.py. Run: python3 test_factcheck.py"""
import os, tempfile
from factcheck import check_quotes, check_numbers, check_quote_parts

d = tempfile.mkdtemp()
open(os.path.join(d, "s1.txt"), "w").write(
    "The team said it’s “not a certain detection” — yet the   data\nshow a second jet, they added.\n")
F = lambda i, q: {"id": i, "text": "x", "quote": q, "source": "s1"}

kept, errs = check_quotes({"facts": [
    F("f1", "THE TEAM said it's \"not a certain detection\" - yet the data show a second jet."),  # normalisation + trailing .
    F("f2", "the data show a second jet"),             # 26 chars, spans the newline
    F("f3", "second jet"),                            # too short
    F("f4", "the team said it is a certain detection"),  # not found
    {"id": "f5", "text": "x", "quote": "a" * 30, "source": "s9"}]}, d)
assert [f["id"] for f in kept] == ["f1", "f2"], kept
assert len(errs) == 3 and "too short" in errs[0] and "f4" in errs[1] and "s9" in errs[2], errs

def sb(say="", **params):
    return {"scenes": [{"id": "a", "say": say, "parts": [{"params": params}]}]}
T = lambda *t: [{"text": x} for x in t]

assert check_numbers(sb("In 2026 it cost $583 million."), T("In 2026 it cost 583 million")) == []
assert check_numbers(sb("[tense] 46.7 percent"), T("x")) == ['scene a: "46.7" is not in any fact']
assert check_numbers(sb("about 1,200 people"), T("1200 people")) == []        # commas
assert check_numbers(sb("a 41% rise"), T("a 41 percent rise")) == []           # units
assert check_numbers(sb("1/16 of it"), T("one-sixteenth of it")) == []          # fraction + number word
assert check_numbers(sb("1/16 of it"), T("x")) == ['scene a: "16" is not in any fact']
assert check_numbers(sb("the 16th"), T("the sixteenth")) == []
assert check_numbers(sb("a third, a quarter"), T("x")) == []                    # 3 exempt; "quarter" absent but no digit 4
assert check_numbers(sb("a 4th"), T("a quarter")) == []
assert check_numbers(sb("half of 23.9"), T("23.86")) == []                      # 1% tolerance
assert check_numbers(sb("24.5"), T("23.86")) != []
assert check_numbers(sb("2.1 billion"), T("2100 million")) == []                # /1000
assert check_numbers(sb("0, 1, 2 and 3 things"), T("x")) == []                  # exempt
assert check_numbers(sb("4 things"), T("x")) != []
assert check_numbers(sb("[beat 77] hello"), T("x")) == []                       # tags ignored
assert check_numbers(sb("23", ), T("twenty-three")) == []
p = sb("hi", image="img99.jpg", ringAt="n55", at="n77", target={"x": 99, "y": 88},
       lines=["Costs $583", {"text": "in 1999", "at": "in"}])
assert check_numbers(p, T("it costs 583")) == ['scene a: "1999" is not in any fact'], check_numbers(p, T("it costs 583"))

# quote scenes show words as someone's own: they must appear verbatim (case, punctuation and line breaks aside) in a source page
qsb = lambda *lines: {"scenes": [{"id": "q", "say": "x", "parts": [{"blueprint": "quote", "params": {"lines": [{"text": l} for l in lines], "who": "A"}}]}]}
src = "Meta said: \u201cWe will NOT stop building\u201d \u2014 not ever, it added."
assert check_quote_parts(qsb("We will not", "stop building"), src) == []
assert check_quote_parts(qsb("We will never", "stop building"), src) == ['scene q: quote "We will never stop building" is not in the source text; quote the source word for word or use a statement']
assert check_quote_parts(sb("hi", lines=["anything"]), src) == []                 # only quote scenes are checked
print("ok")
