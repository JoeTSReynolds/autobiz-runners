# Offline tests for the sources website: render's description links to the video's page, and `site` merges the live
# catalogue with the lane's own entries, builds every page and deploys them. A local server stands in for the live
# site and a fake `npx` for wrangler. Run: python3 test_site.py
import http.server, json, os, subprocess, sys, tempfile, threading
from pathlib import Path

here = Path(__file__).parent
sys.path.insert(0, str(here))
import stage  # noqa: E402

OLD = {"slug": "15d4e39b066f426ba62e0e90aaefa651", "lane": "technology", "channelUrl": "https://www.youtube.com/channel/UC6hSd2TBLkecq2nIkTxmFPA",
       "channelName": "JTSR Tech", "title": "An older story", "summary": "Old summary.", "publishedAt": "2026-09-20T10:00:00+00:00",
       "videoId": "aZ8mG1HADTk", "sources": [{"label": "Old source", "url": "https://example.com/old", "detail": ""}], "credits": [], "limitations": []}

# render: the description is the story plus one link, never the source list
meta = stage.publish_meta({"brief": {"story": "Webb saw a thing.", "facts": [{"source": "https://nasa.gov/a"}]}}, {"title": "Webb Sees A Thing!", "credit": "Photo: NASA"}, "space")
assert meta["siteSlug"].endswith("-webb-sees-a-thing"), meta
assert meta["meta"]["description"] == f"Webb saw a thing.\n\nSources and media credits: https://jtsr-newsroom.pages.dev/videos/{meta['siteSlug']}/", meta
assert "nasa.gov" not in meta["meta"]["description"] and "Photo" not in meta["meta"]["description"]


class Live(http.server.BaseHTTPRequestHandler):
    body = None  # None answers 404

    def do_GET(self):
        ok = self.path == "/catalog.json" and Live.body is not None
        self.send_response(200 if ok else 404); self.end_headers()
        if ok:
            self.wfile.write(Live.body)

    def log_message(self, *a):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), Live)
threading.Thread(target=server.serve_forever, daemon=True).start()

job = {"lane": "tech", "siteSlug": "2026-10-22-chips-get-smaller", "meta": {"title": "Chips <script>x</script> Get Smaller"},
       "brief": {"story": "Chips shrank again.", "images": [{"credit": "Jane Doe (CC BY 4.0)", "page": "https://commons.wikimedia.org/wiki/File:Chip.jpg"},
                                                           {"credit": "Bad link (CC0)", "page": "javascript:alert(1)"}]},
       "sources": [{"id": "s1", "url": "https://example.com/chips", "title": "Chips story"}, {"id": "s2", "url": "http://insecure.example/x", "title": "Plain http"}],
       "facts": {"caution": "Figures are the maker's own."}, "youtube": {"videoId": "dQw4w9WgXcQ"}}


def run_site(d):
    bin_dir = d / "bin"; bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "npx"  # records its arguments and keeps a copy of what it was asked to deploy
    fake.write_text(f"#!/bin/sh\necho \"$@\" > {d}/npx-args\ncp -R \"$5\" {d}/deployed\n"); fake.chmod(0o755)
    (d / "job.json").write_text(json.dumps(job)); (d / "cfg.json").write_text("{}")
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "NEWSROOM_SITE_URL": f"http://127.0.0.1:{server.server_port}",
           "NEWSROOM_SITE_CLOUDFLARE_PROJECT": "jtsr-newsroom"}
    return subprocess.run([sys.executable, "-B", str(here / "stage.py"), "site", "--run", str(d), "--state", str(d / "state"),
                           "--job", str(d / "job.json"), "--config", str(d / "cfg.json"), "--out", str(d / "out.json")], env=env, capture_output=True, text=True)


# the live catalogue is kept, the new video is added, every page is built and deployed
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    Live.body = json.dumps({"videos": [OLD]}).encode()
    r = run_site(d)
    assert r.returncode == 0, r.stderr
    assert json.loads((d / "out.json").read_text())["port"] == "next"
    args = (d / "npx-args").read_text().split()
    assert "pages" in args and "deploy" in args and args[args.index("--project-name") + 1] == "jtsr-newsroom", args
    site = d / "deployed"
    videos = json.loads((site / "catalog.json").read_text())["videos"]
    assert [v["slug"] for v in videos] == [job["siteSlug"], OLD["slug"]], videos
    new = videos[0]
    assert new["videoId"] == "dQw4w9WgXcQ" and new["lane"] == "technology" and new["channelUrl"] == "https://www.youtube.com/@JTSRTech", new
    assert [s["url"] for s in new["sources"]] == ["https://example.com/chips"], new["sources"]  # http links are dropped
    assert [c["url"] for c in new["credits"]] == ["https://commons.wikimedia.org/wiki/File:Chip.jpg"], new["credits"]
    assert new["limitations"] == [{"text": "Figures are the maker's own.", "sources": []}], new
    page = (site / "videos" / job["siteSlug"] / "index.html").read_text()
    assert "https://example.com/chips" in page and "Jane Doe" in page and "dQw4w9WgXcQ" in page
    assert "<script>x" not in page and "&lt;script&gt;" in page
    assert (site / "videos" / OLD["slug"] / "index.html").is_file() and (site / "channels" / "technology" / "index.html").is_file()
    assert (site / "assets" / "style.css").is_file() and "An older story" in (site / "index.html").read_text()
    own = json.loads((d / "state" / "site-entries.json").read_text())
    assert [e["slug"] for e in own] == [job["siteSlug"]], own

# no live catalogue: nothing is deployed (that would wipe the site), but the entry waits in state for the next run
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    Live.body = None
    r = run_site(d)
    assert r.returncode != 0 and "catalog" in r.stderr.lower(), r.stderr
    assert not (d / "npx-args").exists()
    assert [e["slug"] for e in json.loads((d / "state" / "site-entries.json").read_text())] == [job["siteSlug"]]

# a slug from the live catalogue becomes a folder name, so one that could escape the site folder is refused
import newsroom_site  # noqa: E402
try:
    newsroom_site.build([{**OLD, "slug": "../escape"}], Path(tempfile.mkdtemp()) / "out")
    raise AssertionError("unsafe slug was built")
except ValueError:
    pass

server.shutdown()
print("site tests ok")
