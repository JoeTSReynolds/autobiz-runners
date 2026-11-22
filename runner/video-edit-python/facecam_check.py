import sys, json, subprocess, tempfile, os
# Self-check for facecam.py. Usage: facecam_check.py <sample 1280x720 stream clip with a facecam at (0, 272, 348, 218)> <model.onnx>
sample, model = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))

def detect(video):
    out = subprocess.run([sys.executable, os.path.join(here, "facecam.py"), video, model], capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().split("\n")[-1])

found = detect(sample)
assert found["frame"] == {"w": 1280, "h": 720}, found
cam = found["cam"]
assert cam is not None, "the sample's facecam was not found"
want = (0, 272, 348, 218)
got = (cam["x"], cam["y"], cam["x"] + cam["w"], cam["y"] + cam["h"])
for name, g, w in zip(("left", "top", "right", "bottom"), got, (want[0], want[1], want[0] + want[2], want[1] + want[3])):
    assert abs(g - w) <= 25, "%s edge %d is not within 25 px of %d" % (name, g, w)
with tempfile.TemporaryDirectory() as tmp:
    big = os.path.join(tmp, "face.mp4")  # the face and room cropped tight and scaled up: a full-camera stream
    subprocess.run(["ffmpeg", "-v", "error", "-i", sample, "-vf", "crop=220:124:60:300,scale=1280:720", "-an", big], check=True)
    assert detect(big)["cam"] is None, "a full-face frame must give no facecam"
print("facecam check ok:", cam)
