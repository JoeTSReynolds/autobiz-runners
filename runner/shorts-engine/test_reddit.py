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
    assert port == "next" and [x["id"] for x in out["candidates"]][:1] == ["b2"] and out["laneContext"]["channelName"] == reddit.lane_cfg()["channelName"], out
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
# ---------- parts, series, verdicts ----------
link = lambda i: f'<a href="https://www.reddit.com/r/s/comments/{i}/slug/">my last post</a>'
assert reddit.find_original_id(f"<p>See {link('own111')} and {link('org222')}</p>", "own111") == "org222"
assert reddit.find_original_id("<p>https://redd.it/abc123x was it</p>", "zzz") == "abc123x"
assert reddit.find_original_id(f"<p>{link('own111')}</p>", "own111") is None and reddit.find_original_id("<p>nothing</p>", "x") is None
u = reddit.parse_feed(feed(entry("up111", "UPDATE: it got worse", f"<p>{link('org222')} " + "w " * 400 + "</p>")), "s")[0]
assert u["originalId"] == "org222" and "originalId" not in reddit.parse_feed(feed(entry("n1", "Plain")), "s")[0]
for t in ("UPDATE: x", "Final Update", "My story (Part 2)", "AITA pt 2", "pt. 2 of it", "Update"):
    assert reddit.is_update(t), t
for t in ("Updated my phone", "Apartment 2 party", "AITA for a part"):
    assert not reddit.is_update(t), t

orig = {"id": "org222", "subreddit": "s", "title": "The Original", "text": "o " * 300, "url": "uo"}
upd = {"id": "up111", "subreddit": "s2", "title": "UPDATE", "text": "u " * 300, "url": "uu", "originalId": "org222"}
sc = reddit.series_candidate(upd, orig)
assert sc == {"id": "up111", "originalId": "org222", "subreddit": "s2", "title": "The Original", "text": orig["text"] + "\n\n--- UPDATE ---\n\n" + upd["text"], "url": "uu", "series": True}, sc
assert reddit.series_candidate(upd, None) is None and reddit.series_candidate({**upd, "text": "u " * 4600}, orig) is None

# posts(): series candidates go first; used original, used update id and an unfetchable original are skipped; normal updates are not plain candidates
with tempfile.TemporaryDirectory() as d:
    d = Path(d); (d / "state").mkdir(); (d / "state" / "used.json").write_text('["usedorg"]')
    ub = lambda o: f"<p>{link(o)} " + "w " * 400 + "</p>"
    reddit.fetch_sub = lambda sub, wait=True: reddit.parse_feed(feed(entry("b2", "Fresh one"), entry("up1", "Update", ub("org222")), entry("up2", "Part 2", ub("usedorg")), entry("up3", "Final update", ub("gone99"))), sub)
    reddit.fetch_post = lambda oid, wait=True: dict(orig, id=oid) if oid == "org222" else None
    port, out, _ = reddit.posts({"lane": "reddit"}, {}, d, d / "state")
    ids = [x["id"] for x in out["candidates"]]
    assert ids[0] == "up1" and out["candidates"][0]["series"] and ids.count("up1") == 1 and "up2" not in ids and "up3" not in ids and "b2" in ids, ids
    (d / "state" / "used.json").write_text('["up1"]')
    assert "up1" not in [x["id"] for x in reddit.posts({}, {}, d, d / "state")[1]["candidates"]]

# comments feed: the post entry and bot/deleted comments are skipped
def centry(cid, author, text):
    return f'<entry><author><name>/u/{author}</name></author><title>x</title><content type="html">{escape(f"<div class=md><p>{text}</p></div>")}</content><id>t1_{cid}</id></entry>'
cx = feed(entry("p1", "AITA"), centry("c1", "AutoModerator", "NTA welcome"), centry("c2", "bob", "NTA, clearly"), centry("c3", "SomeBot", "YTA"), centry("c4", "al", "[deleted]"))
assert reddit.parse_comments(cx) == ["NTA, clearly"], reddit.parse_comments(cx)

# verdicts: first token per comment, case-sensitive word match, top 15 only
counts, k = reddit.classify_verdicts(["NTA, obviously", "YTA but NTA", "nta lowercase", "INFO please", "The NTAs", "ESH. NTA", "nah", "NAH really", "no verdict"])
assert counts == {"NTA": 1, "YTA": 1, "ESH": 1, "NAH": 1} and k == 9, (counts, k)
c15, k15 = reddit.classify_verdicts(["YTA"] * 15 + ["NTA"] * 10)
assert c15 == {"YTA": 15} and k15 == 15
assert reddit.verdict_comment({"NTA": 7}, 12) == "🗳️ Reddit's verdict: NOT the jerk (7 of the top 12 comments said NTA)."
assert "they WERE the jerk" in reddit.verdict_comment({"YTA": 2, "NTA": 1}, 5) and "everyone sucks here" in reddit.verdict_comment({"ESH": 3}, 3)
assert "no jerks here" in reddit.verdict_comment({"NAH": 4}, 8)
assert reddit.verdict_comment({"NTA": 2}, 9) is None and reddit.verdict_comment({}, 0) is None

# multi-part validation: parts list of 2 to 3, each part checked, all but the last end on a follow line
mk = lambda n, tail="": {"hook": w(10), "script": w(n) + tail, "title": "It gets worse"}
two = {"id": "a1", "parts": [mk(130, " Follow so you don't miss part two!"), mk(140)]}
assert reddit.check_story(two, cands) == []
three = {"id": "a1", "parts": [mk(130, " Follow for part 2!"), mk(130, " Follow so you don't miss part three!"), mk(200)]}
assert reddit.check_story(three, cands) == []  # parts may be up to 220 words
e = reddit.check_story({"id": "a1", "parts": [mk(130), mk(140)]}, cands)
assert e == ['parts[1] script must end on the cliffhanger with a line like "Follow so you don\'t miss part two!"'], e
e = reddit.check_story({"id": "a1", "parts": [mk(130, " Follow for part 2!"), mk(130, " Follow for part 2!"), mk(140)]}, cands)
assert len(e) == 1 and e[0].startswith("parts[2]") and "part three" in e[0], e
assert reddit.check_story({"id": "a1", "parts": [mk(130, " part two")]}, cands) and reddit.check_story({"id": "a1", "parts": [mk(130, " part two")] * 4}, cands)
assert reddit.check_story({"id": "a1", "parts": "x"}, cands)
e = reddit.check_story({"id": "a1", "parts": [mk(130, " part two"), {"hook": w(2), "script": w(10), "title": ""}]}, cands)
assert len(e) == 3 and all(x.startswith("parts[2] ") for x in e), e
assert len(reddit.check_story({"id": "a1", "parts": [mk(130, " part two"), mk(221)]}, cands)) == 1
assert reddit.check_story({**good, "question": "x" * 151}, cands) and reddit.check_story({**good, "question": "Ever?"}, cands) == []

# length rule: every part (and a single story) must run 30 to 58 s
assert reddit.length_error("script", 140, 44.0) is None and reddit.length_error("script", 140, 30.0) is None and reddit.length_error("script", 140, 58.0) is None
e = reddit.length_error("parts[2]", 100, 20.0)
assert e.startswith("parts[2] narration is 20s") and "add about 120 words" in e and "merge" in e, e
e = reddit.length_error("script", 200, 70.0)
assert "70s" in e and "cut about" in e, e

# titles, descriptions, tags
assert reddit.make_title("My story") == "My story | Reddit Stories ❣️"
assert reddit.make_title("My story", 1) == "My story (Part 1) | Reddit Stories ❣️" and reddit.make_title("S", 3).endswith("(Part 3) | Reddit Stories ❣️")
long_t = reddit.make_title("x" * 200, 2)
assert len(long_t) == 100 and long_t.endswith("…" + " (Part 2) | Reddit Stories ❣️"), long_t
m = reddit.build_meta("My story", "C?")
assert m == {"title": "My story | Reddit Stories ❣️", "description": "My story | Reddit Stories ❣️", "tags": ["Reddit stories", "Reddit story", "Redditreading", "Redditpost", "unlimited story", "yt shorts"], "hashtags": [], "comment": "C?"}, m
assert "comment" not in reddit.build_meta("t", None) and reddit.build_meta("t", None, 2)["title"] == "t (Part 2) | Reddit Stories ❣️"

# comments per part: question on all but the last, verdict (else question) on the last
# every comment asks for an opinion and ends asking for a subscribe; AITA asks "jerk or not" and then gives Reddit's verdict
SUB = "Subscribe for a new story every day ❣️"
assert reddit.part_comments(1, "Would you? 👇", None, False) == ["Would you? 👇\n\n" + SUB]
assert reddit.part_comments(1, None, None, False) == ["What would you have done? 👇\n\n" + SUB]
assert reddit.part_comments(1, "Q?", "🗳️ V.", True) == ["Jerk or NOT the jerk? Tell us below 👇\n\n🗳️ V.\n\n" + SUB]
assert reddit.part_comments(1, "Q?", None, True) == ["Jerk or NOT the jerk? Tell us below 👇\n\n" + SUB]
cm = reddit.part_comments(3, "Q?", "🗳️ V.", True)
assert cm[0] == "Q?\n\nPart 2 is already up on the channel! Subscribe so you never miss a part ❣️", cm[0]
assert cm[1].startswith("Q?") and "Part 3 is already up" in cm[1] and cm[2].endswith(SUB) and "🗳️ V." in cm[2], cm

# nextpart mode: records the published id, then hands over the next part with a link to part 1
pm = lambda i: {"title": f"T{i}", "description": f"T{i}", "tags": ["a"], "hashtags": []}
parts = [{"short": {"file": "short.mp4"}, "meta": pm(1)}, {"short": {"file": "short2.mp4"}, "meta": pm(2)}, {"short": {"file": "short3.mp4"}, "meta": pm(3)}]
j = {"parts": parts, "partIndex": 0, "youtube": {"videoId": "v1"}}
port, out, _ = reddit.nextpart(j, {}, Path("."), Path("."))
assert port == "next" and out["partIndex"] == 1 and out["partVideoIds"] == ["v1"] and out["short"] == {"file": "short2.mp4"}, out
assert out["meta"]["description"] == "T2\n\nPart 1: https://youtube.com/shorts/v1" and out["meta"]["title"] == "T2"
port, out, _ = reddit.nextpart({**j, **out, "youtube": {"videoId": "v2"}}, {}, Path("."), Path("."))
assert port == "next" and out["partIndex"] == 2 and out["partVideoIds"] == ["v1", "v2"] and out["meta"]["description"] == "T3\n\nPart 1: https://youtube.com/shorts/v1", out
assert reddit.nextpart({**j, "partIndex": 2, "youtube": {"videoId": "v3"}, "partVideoIds": ["v1", "v2"]}, {}, Path("."), Path("."))[0] == "missing"
assert reddit.nextpart({"parts": parts[:1], "partIndex": 0, "youtube": {"videoId": "v1"}}, {}, Path("."), Path("."))[0] == "missing"
assert reddit.nextpart({}, {}, Path("."), Path("."))[0] == "missing"
out = reddit.nextpart({**j, "youtube": {}}, {}, Path("."), Path("."))[1]
assert out["meta"]["description"] == "T2" and out["partVideoIds"] == [None]

# record also stores originalId (from the story or its candidate)
with tempfile.TemporaryDirectory() as d:
    d = Path(d); st = d / "state"
    reddit.record({"story": {"id": "up1"}, "candidates": [{"id": "up1", "originalId": "org9"}]}, {}, d, st)
    assert json.loads((st / "used.json").read_text()) == ["up1", "org9"]
print("reddit tests ok")

# b-roll overlay text: a shot with burned-in captions or banners is dropped; small @handle watermarks are allowed
box = lambda text, conf: [[[0, 0], [1, 0], [1, 1], [0, 1]], text, conf]
assert reddit.has_overlay_text([box("Ranking Best", 1.0), box("AI ASMR", 0.94)])
assert reddit.has_overlay_text([box("NEWVIDEOONCHANNEL", 1.0)])
assert not reddit.has_overlay_text([box("@sand.tagious", 0.99)])
assert not reddit.has_overlay_text([box("ab", 0.99), box("SO", 0.68), box("NICE", 0.5)])
assert not reddit.has_overlay_text(None)
print("overlay tests ok")

# end card: a part that ends "Follow so you don't miss part two!" shows the follow card from "Follow" to the end, without word captions
cliff = {"duration": 6.0, "scenes": [
    {"id": "hook", "start": 0, "end": 1.0, "words": [{"w": "Hi", "s": 0.1, "e": 0.4}]},
    {"id": "body", "start": 1.0, "end": 6.0, "words": [{"w": "Then", "s": 1.2, "e": 1.5}, {"w": "silence.", "s": 1.6, "e": 2.2},
        {"w": "Follow", "s": 3.0, "e": 3.3}, {"w": "so", "s": 3.3, "e": 3.4}, {"w": "part", "s": 3.6, "e": 3.8}, {"w": "two!", "s": 3.8, "e": 4.2}]}]}
assert reddit.follow_start(cliff) == 3.0
assert reddit.follow_start(timing) is None  # a single or last part has no follow line
ass = reddit.build_ass(cliff, "Hook line here", next_part=2, end=4.6)
words = [l.rsplit(",", 1)[-1] for l in ass.splitlines() if l.startswith("Dialogue") and ",Word," in l]
assert words[-1].endswith("silence.") and not any("Follow" in x for x in words), words
cards = [l for l in ass.splitlines() if ",Card," in l]
assert len(cards) == 2 and cards[1].split(",")[1:3] == ["0:00:03.00", "0:00:04.60"] and "Part 2 is up next!" in cards[1], cards
print("follow card tests ok")
