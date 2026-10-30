# Offline tests for reddit.py (the Reddit stories lane). No network, no ffmpeg. Run: python3 test_reddit.py
import json, sys, tempfile
from html import escape
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))
import reddit  # noqa: E402

BODY = "<p>" + ("I was a kid and it was the strangest day. " * 20) + "</p> <p>Then &amp; it ended &#39;fine&#39;.</p>"


def entry(pid, title, body=BODY):
    html = f'<!-- SC_OFF --><div class="md">{body}</div><!-- SC_ON --> &#32; submitted by &#32; <a href="u">/u/x</a> <br/><span><a href="l">[link]</a></span>'
    return (f'<entry><title>{escape(title)}</title><content type="html">{escape(html)}</content><id>t3_{pid}</id>'
            f'<link href="https://www.reddit.com/r/s/comments/{pid}/slug/" /></entry>')


def feed(*entries):
    return '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">' + "".join(entries) + "</feed>"


# RSS parsing: id without t3_, plain text with paragraph breaks, entities decoded, the "submitted by" footer cut
c = reddit.parse_feed(feed(entry("a1", "AITA for this?")), "s")[0]
assert (c["id"], c["subreddit"], c["title"]) == ("a1", "s", "AITA for this?"), c
assert c["url"] == "https://www.reddit.com/r/s/comments/a1/slug/", c
assert "\n\n" in c["text"] and "&" in c["text"] and "'fine'" in c["text"] and "submitted by" not in c["text"] and "<" not in c["text"], c["text"][-80:]

# filters: 600-5000 chars, removed/deleted, UPDATE follow-ups, used ids
raw = [dict(id=i, subreddit="s", title=t, text=x, url="u") for i, t, x in [
    ("ok", "Fine", "w " * 400), ("short", "Short", "w " * 100), ("rm", "Gone", "[removed]" + " w" * 400), ("del", "Gone", "[deleted]"),
    ("up", "UPDATE: it got worse", "w " * 400), ("up2", "Update on my story", "w " * 400), ("used", "Used", "w " * 400), ("long", "Long", "w " * 3000)]]
kept = reddit.keep(raw, {"used"})
assert [k["id"] for k in kept] == ["ok"], [k["id"] for k in kept]  # 6000 chars is over the 5000 limit: dropped, not cut

# round robin across subreddits, capped
subs = {s: [dict(id=f"{s}{i}", subreddit=s, title="t", text="w " * 400, url="u") for i in range(10)] for s in "abc"}
mixed = reddit.round_robin(subs, 7)
assert [m["id"] for m in mixed] == ["a0", "b0", "c0", "a1", "b1", "c1", "a2"], [m["id"] for m in mixed]

# posts(): no network when fetch is stubbed; missing when nothing is usable; used ids excluded
with tempfile.TemporaryDirectory() as d:
    d = Path(d); (d / "state").mkdir(); (d / "state" / "used.json").write_text('["a1"]')
    reddit.fetch_sub = lambda sub, wait=True: reddit.parse_feed(feed(entry("a1", "Used one"), entry("b2", "Fresh one")), sub)
    port, out, _ = reddit.posts({"lane": "reddit"}, {}, d, d / "state")
    assert port == "next" and [x["id"] for x in out["candidates"]][:1] == ["b2"] and out["laneContext"]["channelName"] == "Reddit Stories", out
    assert "a1" not in [x["id"] for x in out["candidates"]]
    reddit.fetch_sub = lambda sub, wait=True: []
    assert reddit.posts({}, {}, d, d / "state")[0] == "missing"

# archive fallback maps the JSON fields to candidates
js = {"data": [{"id": "z9", "title": "T", "selftext": "<b>x</b> " * 300, "score": 5, "num_comments": 2, "permalink": "/r/s/comments/z9/t/"}]}
z = reddit.parse_archive(js, "s")[0]
assert (z["id"], z["url"]) == ("z9", "https://www.reddit.com/r/s/comments/z9/t/"), z

# check_story
cands = [{"id": "a1"}]
w = lambda n: " ".join(["word"] * n)
good = {"id": "a1", "hook": w(10), "script": w(140), "title": "I never saw it coming"}
assert reddit.check_story(good, cands) == []
assert reddit.check_story("x", cands) and reddit.check_story({}, cands)
bad = reddit.check_story({"id": "nope", "hook": w(3), "script": w(50), "title": ""}, cands)
assert len(bad) == 4 and "id" in bad[0] and "hook" in bad[1] and "script" in bad[2] and "title" in bad[3], bad
assert len(reddit.check_story({**good, "script": w(200)}, cands)) == 1
assert len(reddit.check_story({**good, "title": "x" * 71}, cands)) == 1

# ASS: one word per dialogue, shown until the next word starts, last word +0.3 s, hook scene excluded, escaping
timing = {"duration": 5.0, "scenes": [
    {"id": "hook", "start": 0, "end": 1.5, "words": [{"w": "Hi", "s": 0.1, "e": 0.4}]},
    {"id": "body", "start": 1.5, "end": 5.0, "words": [{"w": "Hello", "s": 1.6, "e": 1.9}, {"w": "{x}\\", "s": 2.0, "e": 2.4}, {"w": "end.", "s": 2.6, "e": 3.0}]}]}
ass = reddit.build_ass(timing, "Everyone mocked my mom's strange rule until that night.")
words = [l for l in ass.splitlines() if l.startswith("Dialogue") and "Word" in l]
assert len(words) == 3 and "Hi" not in "".join(words), words
assert words[0].startswith("Dialogue: 0,0:00:01.60,0:00:02.00,Word") and words[0].endswith("Hello"), words[0]
assert words[2].split(",")[1:3] == ["0:00:02.60", "0:00:03.30"] and words[2].endswith("end."), words[2]
assert "\\{x\\}\\\\" in words[1] or "\\{x\\}" in words[1], words[1]
assert "PlayResX: 1080" in ass and "Lilita One" in ass
card = [l for l in ass.splitlines() if "Card" in l and l.startswith("Dialogue")]
assert len(card) == 1 and card[0].split(",")[1:3] == ["0:00:00.00", "0:00:01.50"] and "Everyone mocked" in card[0], card

# hook wrapping: <= 3 lines, shrinks for long hooks
lines, size = reddit.wrap_hook("Everyone mocked my mom's strange rule until that night.")
assert len(lines) <= 3 and size <= 60
long_lines, long_size = reddit.wrap_hook(" ".join(["Everyone mocked"] * 10))
assert len(long_lines) <= 3 and long_size < size

# segments: deterministic per seed, never repeated, loops only when short
names = [f"seg_{i:03d}.mp4" for i in range(20)]
a, b = reddit.pick_segments(names, 12, "abc"), reddit.pick_segments(names, 12, "abc")
assert a == b and len(set(a)) == 12 and reddit.pick_segments(names, 12, "xyz") != a
loop = reddit.pick_segments(names[:8], 12, "abc")
assert len(loop) == 12 and set(loop) == set(names[:8])
# two shots from the same source video never play back to back (sample 1 showed the same carcass 5 times)
mixed = [f"seg_{v}_{n:02d}.mp4" for v in ("aaaaaaaaaaa", "b_b_b_b_b_b", "ccccccccccc") for n in range(4)]
for seed in ("abc", "xyz", "1xgifde"):
    order = reddit.pick_segments(mixed, 12, seed)
    assert all(reddit.source_of(x) != reddit.source_of(y) for x, y in zip(order, order[1:])), order

# record: appends the story id, keeps the last 3000
with tempfile.TemporaryDirectory() as d:
    d = Path(d); st = d / "state"; st.mkdir()
    (st / "used.json").write_text(json.dumps([f"o{i}" for i in range(3000)]))
    assert reddit.record({"story": {"id": "new"}}, {}, d, st)[0] == "next"
    used = json.loads((st / "used.json").read_text())
    assert len(used) == 3000 and used[-1] == "new" and used[0] == "o1", (len(used), used[0])
print("reddit tests ok")
