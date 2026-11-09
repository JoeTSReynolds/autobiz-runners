"""Turn caption word lists into the transcript text the storyboard agent reads, windowed to what matters."""
import re
from .sourcerules import fold

TAG = re.compile(r'^[\[(][^\])]*[\])]$')  # [applause] (music)
BLOCK_CAP, TOTAL_CAP = 18000, 60000


def clean(words):
    """Drop sound tags and speaker markers (>>) so phrase matching sees speech only."""
    out = []
    for w in words:
        t = re.sub(r'^>+\s*', '', w['w']).strip()
        if t and not TAG.match(t): out.append(dict(w, w=t))
    return out


def peaks(info, n=3):
    hm = sorted(info.get('heatmap') or [], key=lambda h: -h['value'])[:n]
    return [(h['start_time'] + h['end_time']) / 2 for h in hm]


def window(sents, info, keywords, cap, span=20):
    """Lines '[start-end] text' in time order, at most cap characters: the replay peaks first, then keyword mentions."""
    line = lambda s: f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}"
    if sum(len(line(s)) + 1 for s in sents) <= cap: return '\n'.join(map(line, sents))
    pk = peaks(info)
    near = lambda p: [i for i, s in enumerate(sents) if abs((s['start'] + s['end']) / 2 - p) <= span]
    kws = [fold(k) for k in keywords if k]
    hit = [i for i, s in enumerate(sents) if any(k in fold(s['text']) for k in kws)]
    order = (near(pk[0]) if pk else []) + hit + [i for p in pk[1:] for i in near(p)] + ([] if pk or hit else list(range(len(sents))))
    chosen, used = set(), 0
    for i in order:
        if i in chosen or used + len(line(sents[i])) + 1 > cap: continue
        chosen.add(i); used += len(line(sents[i])) + 1
    return '\n'.join(line(sents[i]) for i in sorted(chosen))


def block(meta, sents, info, keywords, cap=BLOCK_CAP):
    head = f"### {meta['id']} | {meta['title']} | {meta['channel']} | {meta['duration']} s | {meta['uploaded']}"
    return head + '\n' + window(sents, info, keywords, cap - len(head) - 1)


def build(sources, keywords):
    """sources [(meta, sentences, info)] -> text, at most TOTAL_CAP characters."""
    parts, left = [], TOTAL_CAP
    for meta, sents, info in sources:
        if left < 500: break
        b = block(meta, sents, info, keywords, min(BLOCK_CAP, left - 2))
        parts.append(b); left -= len(b) + 2
    return '\n\n'.join(parts)
