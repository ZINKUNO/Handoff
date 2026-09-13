"""Assemble the narrated pitch video.

Each slide is held for its narration plus a beat, with a slow push-in and a
crossfade into the next. Where the deck shows the app running, the live tour
footage is cut in over the slide's narration. Captions are burned in from the
narration text so the video reads with the sound off.
"""
import json
import pathlib
import subprocess
import textwrap

S = pathlib.Path(__file__).parent / "work"
FPS = 30
W, H = 1920, 1080
cues = json.loads((S / "narration" / "pitch.json").read_text())
slides = sorted((S / "slides").glob("slide.*.png"))
assert len(slides) == len(cues), (len(slides), len(cues))

# Live footage: which slide gets which clip. Marks come from the tour log.
marks = {}
mp = S / "tour" / "marks.txt"
if mp.exists():
    for line in mp.read_text().splitlines():
        t, name = line.split("\t", 1)
        marks.setdefault(name.split("  ")[0].strip(), float(t))
tour = S / "tour" / "tour.mp4"
have_tour = tour.exists() and marks

def clip_for(title):
    """(start, end) in the tour video for a slide, or None."""
    if not have_tour:
        return None
    ends = sorted(marks.values())
    def span(name, length):
        if name not in marks: return None
        t0 = marks[name]
        return (t0, t0 + length)
    return {
        "say it once": span("run now", 9.5),
        "it runs": span("inspector run", 8),
        "the gate": span("orb waiting", 7),
        "the decision": span("decision screen", 11),
        "it gets quieter": span("memory", 4.5),
        "eight apps": span("credentials", 4),
        "three surfaces": span("orb", 5),
    }.get(title)

work = S / "pitch_work"; work.mkdir(exist_ok=True)
segments, srt, t_cursor = [], [], 0.0
PAD, XF = 0.9, 0.5

def fmt(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"

for i, (png, cue) in enumerate(zip(slides, cues)):
    dur = cue["duration"] + PAD
    out = work / f"seg{i:02d}.mp4"
    clip = clip_for(cue["title"])
    if clip and clip[1] - clip[0] < dur - 2:
        # Slide first, then the live footage for the remainder.
        slide_part = dur - (clip[1] - clip[0])
        a = work / f"seg{i:02d}_a.mp4"; b = work / f"seg{i:02d}_b.mp4"
        subprocess.run(["ffmpeg","-y","-v","error","-loop","1","-framerate",str(FPS),"-i",str(png),"-t",f"{slide_part:.3f}",
                        "-vf",f"scale=8000:-1,zoompan=z='min(zoom+0.0006,1.06)':d={int(slide_part*FPS)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},format=yuv420p",
                        "-c:v","libx264","-preset","medium","-crf","17","-an",str(a)], check=True)
        subprocess.run(["ffmpeg","-y","-v","error","-ss",f"{clip[0]:.3f}","-t",f"{clip[1]-clip[0]:.3f}","-i",str(tour),
                        "-vf",f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p",
                        "-c:v","libx264","-preset","medium","-crf","17","-an",str(b)], check=True)
        subprocess.run(["ffmpeg","-y","-v","error","-i",str(a),"-i",str(b),"-filter_complex",
                        f"[0][1]xfade=transition=fade:duration=0.4:offset={slide_part-0.4:.3f},format=yuv420p","-c:v","libx264","-preset","medium","-crf","17","-an",str(out)], check=True)
    else:
        subprocess.run(["ffmpeg","-y","-v","error","-loop","1","-framerate",str(FPS),"-i",str(png),"-t",f"{dur:.3f}",
                        "-vf",f"scale=8000:-1,zoompan=z='min(zoom+0.0006,1.06)':d={int(dur*FPS)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},format=yuv420p",
                        "-c:v","libx264","-preset","medium","-crf","17","-an",str(out)], check=True)
    segments.append((out, dur, cue["file"]))

    # Captions: split the narration into readable lines spread over its duration.
    words = cue["text"].split()
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(" ".join(cur)) > 78 or w.endswith((".", "?", "!")) and len(" ".join(cur)) > 40:
            chunks.append(" ".join(cur)); cur = []
    if cur: chunks.append(" ".join(cur))
    total_chars = sum(len(c) for c in chunks) or 1
    tt = t_cursor + 0.15
    for c in chunks:
        share = cue["duration"] * len(c) / total_chars
        srt.append(f"{len(srt)+1}\n{fmt(tt)} --> {fmt(tt+share-0.05)}\n{textwrap.fill(c, 60)}\n")
        tt += share
    t_cursor += dur - XF  # crossfades overlap by XF

# Crossfade every segment into the next.
n = len(segments)
inputs = []
for seg, _, _ in segments: inputs += ["-i", str(seg)]
filt, prev, offset = [], "[0:v]", 0.0
for i in range(1, n):
    offset += segments[i-1][1] - XF
    outl = f"[v{i}]" if i < n-1 else "[vout]"
    filt.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XF}:offset={offset:.3f}{outl}")
    prev = outl
subprocess.run(["ffmpeg","-y","-v","error",*inputs,"-filter_complex",";".join(filt),"-map","[vout]","-c:v","libx264","-preset","medium","-crf","17","-pix_fmt","yuv420p",str(work/"video.mp4")], check=True)

# Narration placed at each slide's start.
ainputs, afilt, t0 = [], [], 0.0
for i, (_, dur, audio) in enumerate(segments):
    ainputs += ["-i", audio]
    afilt.append(f"[{i}]adelay={int(t0*1000)}|{int(t0*1000)}[a{i}]")
    t0 += dur - XF
total = t0 + XF
mix = "".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:dropout_transition=0,apad=whole_dur={total:.3f}[out]"
subprocess.run(["ffmpeg","-y","-v","error",*ainputs,"-filter_complex",";".join(afilt)+";"+mix,"-map","[out]","-ar","48000","-c:a","aac","-b:a","192k",str(work/"narration.m4a")], check=True)

(work/"captions.srt").write_text("\n".join(srt))
style = "FontName=Instrument Sans,FontSize=13,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=4,BackColour=&H80000000,Outline=0,Shadow=0,MarginV=42,Alignment=2"
subprocess.run(["ffmpeg","-y","-v","error","-i",str(work/"video.mp4"),"-i",str(work/"narration.m4a"),
                "-vf",f"subtitles={work/'captions.srt'}:force_style='{style}'",
                "-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p","-c:a","copy","-shortest",str(S/"handoff-pitch.mp4")], check=True)
print(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_type,width,height","-of","default=nw=1",str(S/"handoff-pitch.mp4")],capture_output=True,text=True).stdout)
print("live clips used:", {c["title"]: clip_for(c["title"]) for c in cues if clip_for(c["title"])})
