# Photo choice for case-file shots: least used first, the query's own photo preferred, never the same photo twice in a row
# (live 2026-11-07: 10 photo shots cut between 2 pictures). Run: python3 formats/test_casefile_pick.py (prints ok)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trending.formats.casefile import pick_photo

P = [{'query': 'court', 'file': 'c'}, {'query': 'Brand', 'file': 'b1'}, {'query': 'Brand', 'file': 'b2'}, {'query': 'court', 'file': 'c2'}]
uses, last, seq = {}, None, []
for q in ['court', 'Brand', 'Brand', None, None, None, None, None]:
    p = pick_photo(P, uses, q, last)
    seq.append(p['file']); last = p['file']
assert seq[:3] == ['c', 'b1', 'b2'], seq                       # each query gets its own unused photo first
assert all(a != b for a, b in zip(seq, seq[1:])), seq            # never twice in a row
assert sorted(uses.values()) == [2, 2, 2, 2], uses               # spread evenly over the pool
assert pick_photo([], {}, 'x', None) is None
assert pick_photo(P[:1], {}, None, 'c')['file'] == 'c'           # a single photo is still better than none
print('ok')
