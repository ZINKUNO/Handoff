"""Frame-render explainer.html against the narration timeline, then mux narration in."""
import json
import pathlib
import shutil
import subprocess

from playwright.sync_api import sync_playwright

S = pathlib.Path(__file__).parent / "work"
FPS = 30
cues = json.loads((S/"narration"/"explainer.json").read_text())
PAD = {"title": 1.2, "close": 2.2}
timeline, t = [], 0.0
for c in cues:
    dur = c["duration"] + PAD.get(c["id"], 1.0)
    timeline.append({"id": c["id"], "start": round(t, 3), "dur": round(dur, 3), "audio": c["file"]})
    t += dur
total = t
(S/"explainer_timeline.json").write_text(json.dumps(timeline, indent=2))
print(f"total {total:.1f}s, {int(total*FPS)} frames", flush=True)

frames = S/"frames_explainer"
if frames.exists(): shutil.rmtree(frames)
frames.mkdir()

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl"])
    pg = b.new_page(viewport={"width":1920, "height":1080}, device_scale_factor=1)
    pg.goto((S/"explainer.html").as_uri()); pg.wait_for_load_state("networkidle")
    pg.evaluate("window.ready"); pg.wait_for_timeout(800)
    pg.evaluate("tl => window.build(tl)", timeline)
    n = int(total*FPS)
    for i in range(n):
        pg.evaluate("t => window.seek(t)", i/FPS)
        pg.screenshot(path=str(frames/f"f{i:05d}.jpg"), type="jpeg", quality=92)
        if i % 300 == 0: print(f"  frame {i}/{n}", flush=True)
    b.close()

# Video from frames.
subprocess.run(["ffmpeg","-y","-v","error","-framerate",str(FPS),"-i",str(frames/"f%05d.jpg"),
                "-c:v","libx264","-preset","medium","-crf","17","-pix_fmt","yuv420p",str(S/"explainer_silent.mp4")], check=True)

# Narration placed at each scene's start, mixed onto one track the length of the video.
inputs, filt = [], []
for i, sc in enumerate(timeline):
    inputs += ["-i", sc["audio"]]
    filt.append(f"[{i}]adelay={int(sc['start']*1000)}|{int(sc['start']*1000)}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(timeline))) + f"amix=inputs={len(timeline)}:normalize=0:dropout_transition=0,apad=whole_dur={total:.3f}[out]"
subprocess.run(["ffmpeg","-y","-v","error",*inputs,"-filter_complex",";".join(filt)+";"+mix,"-map","[out]","-ar","48000","-c:a","aac","-b:a","192k",str(S/"explainer_narration.m4a")], check=True)
subprocess.run(["ffmpeg","-y","-v","error","-i",str(S/"explainer_silent.mp4"),"-i",str(S/"explainer_narration.m4a"),
                "-c:v","copy","-c:a","copy","-shortest",str(S/"handoff-explainer.mp4")], check=True)
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_type,width,height","-of","default=nw=1",str(S/"handoff-explainer.mp4")],capture_output=True,text=True).stdout)
