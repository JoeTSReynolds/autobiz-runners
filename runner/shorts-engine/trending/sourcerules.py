"""Per-format source rules for mediaplan, and name folding."""
import re, unicodedata

# dur: source length range in seconds; min: usable sources (with English captions) before the person is rejected; k: sources whose captions we read.
# The duration ranges are this build's choice: the plan only says "a duration range per format".
FORMATS = {
    'tribute': dict(dur=(120, 7200), min=3, k=6),
    'topn': dict(dur=(120, 7200), min=4, k=8),
    'edit': dict(dur=(300, 7200), min=1, k=3),
    'casefile': dict(dur=(30, 1800), min=0, k=2),
}
NOT_PLAYABLE = {'is_live', 'is_upcoming', 'post_live'}
SUFFIX = {'jr', 'sr', 'ii', 'iii', 'iv'}


def fold(s):
    return re.sub(r'[^a-z0-9 ]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower())


def surname(name):
    toks = [t for t in fold(name).split() if t not in SUFFIX]
    return toks[-1] if toks else ''


def usable(e, fmt, sur, excluded):
    lo, hi = FORMATS[fmt]['dur']
    return (e['id'] not in excluded and lo <= (e.get('duration') or 0) <= hi and e.get('live_status') not in NOT_PLAYABLE
            and sur in fold(f"{e.get('title', '')} {e.get('channel', '')}"))
