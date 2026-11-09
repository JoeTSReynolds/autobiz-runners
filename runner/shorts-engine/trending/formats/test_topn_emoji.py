# Offline: the closer's emoji is split from its text and fetched as a Fluent 3D image (same source as video-edit).
# Run: python3 formats/test_topn_emoji.py (engine folder on sys.path, like the other trending tests)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trending.formats import topn

assert topn.split_emoji("STILL DODGING? 👀") == ("STILL DODGING?", "👀")
assert topn.split_emoji("NO EMOJI HERE") == ("NO EMOJI HERE", None)
assert topn.split_emoji("😭 SO SAD") == ("SO SAD", "😭")
base = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/"
assert topn.emoji_urls("👀") == [base + "Eyes/3D/eyes_3d.png", base + "Eyes/Default/3D/eyes_3d_default.png"], topn.emoji_urls("👀")
assert topn.emoji_urls("😭")[0] == base + "Loudly%20crying%20face/3D/loudly_crying_face_3d.png", topn.emoji_urls("😭")
print("ok")
