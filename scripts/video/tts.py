"""Narration: text -> mp3, cached by content hash, retried on the transient errors edge-tts throws."""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time

S = pathlib.Path(__file__).parent / "work"
CACHE = S / "narration" / "cache"; CACHE.mkdir(parents=True, exist_ok=True)
PY = sys.executable
VOICE = "en-US-AndrewMultilingualNeural"

def duration(path):
    out = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(path)],capture_output=True,text=True).stdout.strip()
    return float(out)

def speak(text, rate="-4%"):
    key = hashlib.sha1(f"{VOICE}|{rate}|{text}".encode()).hexdigest()[:16]
    mp3 = CACHE / f"{key}.mp3"
    if mp3.exists() and mp3.stat().st_size > 1000:
        return mp3, duration(mp3)
    for attempt in range(5):
        r = subprocess.run([PY,"-m","edge_tts","--voice",VOICE,f"--rate={rate}","--text",text,"--write-media",str(mp3)],capture_output=True,text=True)
        if r.returncode == 0 and mp3.exists() and mp3.stat().st_size > 1000:
            return mp3, duration(mp3)
        time.sleep(2 + attempt * 3)
    raise RuntimeError(f"tts failed: {text[:60]}… :: {r.stderr[-300:]}")

def clean(text):
    text = text.replace("⏸", ",").replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()

EXPLAINER = [
 ("title",    "Handoff. Built for the Multi-App AI Agent Hackathon. Here is how it works."),
 ("problem",  "Every morning starts the same way. Forty unread emails, three real asks, and twenty-five minutes gone before the first coffee is finished. None of it is hard. It's just every single day."),
 ("sentence", "You describe the job once, in one sentence. Handoff turns it into a workflow: a schedule, the apps it needs, and a line it will not cross."),
 ("run",      "At eight, with nobody watching, it runs. It reads the mail and the calendar together. Files the real asks in Linear. Books the time to actually do them. Archives the noise. Every step, across a real app."),
 ("gate",     "Every action carries a confidence. Above the threshold, it acts alone. Below it, a hook stops the tool before it runs. The code path that would send the email or file the ticket never executes."),
 ("phone",    "The one it can't call goes to your phone, with the answers as buttons. One tap, and the run resumes exactly where it stopped."),
 ("evidence", "Every decision is logged with the confidence it had, whether the agent made it or you did. That log is how you know it works. Not a screenshot. A table anyone can audit."),
 ("learn",    "Your answer becomes a rule. Tomorrow it asks about one fewer thing. It doesn't get louder as it learns. It gets quieter."),
 ("close",    "Handoff. Describe it. Hand it off. It runs."),
]

if __name__ == "__main__":
    which = sys.argv[1]
    if which == "pitch":
        script = pathlib.Path(str(pathlib.Path(__file__).resolve().parents[2] / "docs") + "/pitch/script.md").read_text()
        cues = []
        for m in re.finditer(r"\*\*Slide (\d+) — ([^.]+)\.\*\*\s*(.+)", script):
            text = clean(m.group(3))
            mp3, d = speak(text)
            cues.append({"slide": int(m.group(1)), "title": m.group(2), "text": text, "file": str(mp3), "duration": d})
            print(f"slide {cues[-1]['slide']:2d} {d:6.1f}s  {m.group(2)}", flush=True)
        (S / "narration" / "pitch.json").write_text(json.dumps(cues, indent=2))
        print("pitch total", round(sum(c["duration"] for c in cues), 1), "s")
    elif which == "explainer":
        cues = []
        for sid, text in EXPLAINER:
            mp3, d = speak(text)
            cues.append({"id": sid, "text": text, "file": str(mp3), "duration": d})
            print(f"{sid:9s} {d:6.1f}s", flush=True)
        (S / "narration" / "explainer.json").write_text(json.dumps(cues, indent=2))
        print("explainer total", round(sum(c["duration"] for c in cues), 1), "s")

def demo_cues():
    """The two-minute cut: each '## m:ss – m:ss — title' section's blockquote in VIDEO_SCRIPT.md."""
    doc = pathlib.Path(str(pathlib.Path(__file__).resolve().parents[2] / "docs") + "/VIDEO_SCRIPT.md").read_text()
    cues = []
    for m in re.finditer(r"^## (\d+:\d\d) – (\d+:\d\d) — ([^\n]+)\n(.*?)(?=^## |\Z)", doc, re.M | re.S):
        quotes = re.findall(r"^> (.+)$", m.group(4), re.M)
        # A section can hold two quotes (the phone scene: the buzz, then the tap).
        blocks, cur = [], []
        for q in quotes:
            cur.append(q)
        text = clean(" ".join(cur))
        # split on the screen-change marker: the phone section's second quote starts after a blank
        parts = [p.strip() for p in re.split(r"\n\*\*Screen:\*\*", m.group(4))]
        qs = [clean(" ".join(re.findall(r"^> (.+)$", p, re.M))) for p in parts]
        qs = [q for q in qs if q]
        for j, q in enumerate(qs):
            cues.append({"id": f"{m.group(3).strip().lower().replace(' ', '-')[:24]}-{j}", "start_label": m.group(1), "title": m.group(3).strip(), "text": q})
    return cues

if __name__ == "__main__" and sys.argv[1] == "demo":
    cues = demo_cues()
    for c in cues:
        mp3, d = speak(c["text"])
        c["file"] = str(mp3); c["duration"] = d
        print(f"{c['start_label']:>5} {d:6.1f}s  {c['title']}", flush=True)
    (S / "narration" / "demo.json").write_text(json.dumps(cues, indent=2))
    print("demo total", round(sum(c["duration"] for c in cues), 1), "s")
