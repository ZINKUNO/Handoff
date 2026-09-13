"""The two-minute submission cut: Priya's Monday, told over live footage and the explainer.

Every cue in narration/demo.json gets a shot list — pieces cut from the live
tour (real app) or from the silent explainer render (animation) — filling the
narration's length plus a beat. Cues crossfade; narration sits at each cue's
start; captions are burned in. The hard limit is 120 seconds.
"""
import json
import pathlib
import subprocess
import textwrap

S = pathlib.Path(__file__).parent / "work"
FPS, W, H = 30, 1920, 1080
LIMIT = 120.0

cues = json.loads((S / "narration" / "demo.json").read_text())
scenes = {sc["id"]: sc for sc in json.loads((S / "explainer_timeline.json").read_text())}
marks = {}
for line in (S / "tour" / "marks.txt").read_text().splitlines():
    t, name = line.split("\t", 1)
    marks.setdefault(name.strip(), float(t))
TOUR = S / "tour" / "tour.mp4"
EXPL = S / "explainer_silent.mp4"

def ex(scene, offset=0.0):
    # The piece may never read past its own scene: hold the scene's last frame instead.
    sc = scenes[scene]
    return ("src", EXPL, sc["start"] + offset, sc["start"] + sc["dur"] - 0.45)

def tour(mark, offset=0.0):
    return ("src", TOUR, marks[mark] + offset, None)

# Shot list per cue: (source, start) pieces with a share of the cue's length.
# Shares are fractions of the cue; the last piece absorbs the rounding.
PLAN = {
    0: [(ex("problem", 0.4), 1.0)],
    1: [(tour("workflows", 0.3), 0.3), (ex("sentence", 0.2), 0.7)],
    2: [(tour("run now", 0.0), 0.62), (ex("run", 2.4), 0.38)],
    3: [(ex("gate", 0.3), 0.62), (tour("orb waiting", 0.4), 0.38)],
    4: [(ex("phone", 3.6), 0.45), (tour("decision screen", 0.6), 0.55)],
    5: [(ex("evidence", 0.4), 1.0)],
    6: [(tour("memory", 0.5), 0.5), (ex("close", 0.0), 0.5)],
}

PAD, XF = 0.35, 0.4
work = S / "demo_work"; work.mkdir(exist_ok=True)

def norm(src, start, length, out, limit=None):
    read = length if limit is None else max(0.5, min(length, limit - start))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{read:.3f}", "-i", str(src),
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},"
                           f"tpad=stop_mode=clone:stop_duration={length:.3f},trim=duration={length:.3f},setpts=PTS-STARTPTS,format=yuv420p",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-an", str(out)], check=True)

def xfade_chain(parts, durs, out, xf):
    n = len(parts)
    if n == 1:
        subprocess.run(["cp", str(parts[0]), str(out)]); return
    inputs = []
    for p_ in parts: inputs += ["-i", str(p_)]
    filt, prev, offset = [], "[0:v]", 0.0
    for i in range(1, n):
        offset += durs[i - 1] - xf
        lbl = f"[v{i}]" if i < n - 1 else "[vout]"
        filt.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xf}:offset={offset:.3f}{lbl}")
        prev = lbl
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[vout]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", str(out)], check=True)

# Fit under the limit: shave the pad first, then trim the longest cues' beats.
total = sum(c["duration"] + PAD for c in cues) - XF * (len(cues) - 1)
if total > LIMIT:
    PAD = max(0.1, PAD - (total - LIMIT) / len(cues))
    total = sum(c["duration"] + PAD for c in cues) - XF * (len(cues) - 1)
assert total <= LIMIT + 0.05, f"cut is {total:.1f}s; tighten the narration"

segs, durs = [], []
for i, cue in enumerate(cues):
    dur = cue["duration"] + PAD
    pieces = PLAN[i]
    parts, pdurs, used = [], [], 0.0
    inner_xf = 0.3 if len(pieces) > 1 else 0.0
    span = dur + inner_xf * (len(pieces) - 1)
    for j, ((_, src, start, limit), share) in enumerate(pieces):
        length = round(span * share, 3) if j < len(pieces) - 1 else round(span - used, 3)
        used += length
        out = work / f"c{i:02d}_p{j}.mp4"
        norm(src, start, length, out, limit)
        parts.append(out); pdurs.append(length)
    seg = work / f"c{i:02d}.mp4"
    xfade_chain(parts, pdurs, seg, inner_xf)
    segs.append(seg); durs.append(dur)

xfade_chain(segs, durs, work / "video.mp4", XF)

# Narration at each cue start.
ainputs, afilt, t0 = [], [], 0.0
for i, cue in enumerate(cues):
    ainputs += ["-i", cue["file"]]
    afilt.append(f"[{i}]adelay={int(t0 * 1000)}|{int(t0 * 1000)}[a{i}]")
    t0 += durs[i] - XF
mix = "".join(f"[a{i}]" for i in range(len(cues))) + f"amix=inputs={len(cues)}:normalize=0:dropout_transition=0,apad=whole_dur={total:.3f}[out]"
subprocess.run(["ffmpeg", "-y", "-v", "error", *ainputs, "-filter_complex", ";".join(afilt) + ";" + mix, "-map", "[out]",
                "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(work / "narration.m4a")], check=True)

# Captions.
def fmt(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"
srt, t0 = [], 0.0
for i, cue in enumerate(cues):
    words, chunks, cur = cue["text"].strip().strip('"“”').split(), [], []
    for w in words:
        cur.append(w)
        if len(" ".join(cur)) > 74 or (w.endswith((".", "?", "!")) and len(" ".join(cur)) > 36):
            chunks.append(" ".join(cur)); cur = []
    if cur: chunks.append(" ".join(cur))
    chars = sum(len(c) for c in chunks) or 1
    tt = t0 + 0.1
    for c in chunks:
        share = cue["duration"] * len(c) / chars
        srt.append(f"{len(srt) + 1}\n{fmt(tt)} --> {fmt(tt + share - 0.05)}\n{textwrap.fill(c, 58)}\n")
        tt += share
    t0 += durs[i] - XF
(work / "captions.srt").write_text("\n".join(srt))
style = "FontName=Instrument Sans,FontSize=13,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=4,BackColour=&H80000000,Outline=0,Shadow=0,MarginV=42,Alignment=2"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(work / "video.mp4"), "-i", str(work / "narration.m4a"),
                "-vf", f"subtitles={work / 'captions.srt'}:force_style='{style}'",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest",
                str(S / "handoff-demo-2min.mp4")], check=True)
print(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "default=nw=1",
                      str(S / "handoff-demo-2min.mp4")], capture_output=True, text=True).stdout)
print(f"planned {total:.1f}s, pad {PAD:.2f}s")
