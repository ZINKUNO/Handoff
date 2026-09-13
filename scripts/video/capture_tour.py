"""Drive the real Handoff web app through a run and record it at 1080p.

Offline scripted model + synthetic inbox, so the run is deterministic and always
sets items aside for a human. Nothing here touches a real service. Stills are
cut from the recording afterwards; screenshots mid-recording are avoided.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

S = pathlib.Path(__file__).parent / "work" / "tour"
ROOT = pathlib.Path(__file__).resolve().parents[2]
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
state = S / "state"
shutil.rmtree(state, ignore_errors=True); state.mkdir(parents=True)
shutil.rmtree(S / "raw", ignore_errors=True)

env = dict(os.environ, PYTHONPATH="src", HANDOFF_FAKE_MODEL="true", HANDOFF_MODEL_PROVIDER="fake",
           USE_MOCK_TOOLS="true", HANDOFF_STATE_DIR=str(state), UI_PORT=str(PORT), NOTIFY_CHANNEL="console",
           USE_DYNAMODB="false", USE_AGENTCORE_MEMORY="false", STRANDS_OTEL_ENABLE="false", UI_BASE_URL=BASE)
server = subprocess.Popen([str(ROOT / ".venv-strands/bin/python"), "-m", "uvicorn", "handoff.web.server:app",
                           "--host", "127.0.0.1", "--port", str(PORT)], cwd=ROOT, env=env,
                          stdout=open(S / "server.log", "w"), stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        urllib.request.urlopen(BASE + "/health", timeout=1); break
    except Exception:
        time.sleep(0.5)
else:
    server.kill(); sys.exit("server never came up")

CURSOR_JS = """
(() => {
  let c = null;
  function ensure(){
    if (c && c.isConnected) return c;
    c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = `<svg width="26" height="30" viewBox="0 0 26 30"><path d="M2 2 L2 24 L8 18 L12 28 L16 26 L12 17 L20 17 Z" fill="#111" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>`;
    Object.assign(c.style, {position:'fixed', left:'0px', top:'0px', zIndex:2147483647, pointerEvents:'none',
      transition:'transform 650ms cubic-bezier(.2,.7,.2,1)', transform:'translate(960px,540px)', filter:'drop-shadow(0 2px 4px rgba(0,0,0,.35))'});
    (document.body || document.documentElement).appendChild(c);
    return c;
  }
  window.__glide = (x, y) => { ensure().style.transform = `translate(${x}px,${y}px)`; };
  document.addEventListener('DOMContentLoaded', ensure);
})();
"""

def log(msg): print(f"[tour] {msg}", flush=True)

from playwright.sync_api import sync_playwright

marks = []
total = 0.0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                                  record_video_dir=str(S / "raw"), record_video_size={"width": 1920, "height": 1080})
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        T0 = time.time()

        def mark(name):
            marks.append((round(time.time() - T0, 2), name)); log(f"{marks[-1][0]:6.1f}s {name}  {page.url}")

        def hold(sec, still=None):
            if still: mark(f"still:{still}")
            page.wait_for_timeout(int(sec * 1000))

        def glide_click(locator, settle=0.8):
            locator.first.scroll_into_view_if_needed(); page.wait_for_timeout(300)
            box = locator.first.bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            page.evaluate("([x,y]) => window.__glide(x-3, y-3)", [x, y])
            page.wait_for_timeout(int(settle * 1000))
            page.mouse.click(x, y)

        def goto(path, name, sec, still=None):
            page.goto(BASE + path); page.wait_for_load_state("domcontentloaded"); mark(name)
            hold(sec, still or name)

        # 1. First launch: the welcome wizard.
        goto("/welcome", "welcome", 1.5)
        page.fill("input[name=full_name]", "Priya"); page.wait_for_timeout(400)
        page.fill("input[name=email]", "priya@example.com"); page.wait_for_timeout(400)
        page.fill("input[name=timezone]", "Asia/Kolkata"); page.wait_for_timeout(600)
        page.press("input[name=timezone]", "Enter")
        page.wait_for_url(lambda u: not u.endswith("/welcome"), timeout=8000)
        page.wait_for_load_state("domcontentloaded"); mark("overview")
        hold(4, "overview")

        # 2. The workflows page, and Run now on the inbox triage.
        goto("/platform", "workflows", 3)
        run_btn = page.locator("#flow-inbox-triage-morning button:has-text('Run now')")
        if not run_btn.count():
            run_btn = page.locator("button:has-text('Run now')")
        glide_click(run_btn); mark("run now")
        page.wait_for_timeout(1200)
        hold(4, "run-started")

        runs = json.loads((state / "runs.json").read_text())
        run_id = (runs[-1] if isinstance(runs, list) else list(runs.values())[-1])["run_id"]
        # The orb, amber: the run is waiting on three decisions, cards drawn from its own reasoning.
        goto("/orb", "orb waiting", 6, "orb-waiting")
        goto(f"/inspector/{run_id}", "inspector run", 7, "inspector-run")

        # 3. Every decision the run set aside, answered one by one. Each answer becomes a rule.
        for i in range(3):
            goto("/activity", "activity" if i == 0 else f"activity {i+1}", 2.5 if i == 0 else 1.2, "activity" if i == 0 else None)
            dec = page.locator("a[href^='/decide/']")
            if not dec.count():
                mark("no decision link found"); break
            glide_click(dec); page.wait_for_load_state("domcontentloaded"); mark("decision screen" if i == 0 else f"decision {i+1}")
            hold(6 if i == 0 else 3, "decision" if i == 0 else None)
            choice = page.locator("button[name=action].suggested")
            if not choice.count(): choice = page.locator("button[name=action][value=archive]")
            if not choice.count(): choice = page.locator("button[name=action]")
            glide_click(choice); mark("decided" if i == 0 else f"decided {i+1}")
            page.wait_for_timeout(1200)
            hold(3.5 if i == 0 else 2, "decided" if i == 0 else None)

        # The same run, resumed and finished.
        goto(f"/inspector/{run_id}", "inspector done", 5, "inspector-done")

        # 4. What it learned, what it is connected to, the tool catalogue, the orb.
        goto("/memory", "memory", 4.5)
        goto("/credentials", "credentials", 4)
        goto("/mcp", "mcp", 3.5)
        goto("/orb", "orb", 5)

        total = round(time.time() - T0, 1)
        ctx.close(); browser.close()
finally:
    server.terminate()

raw = next((S / "raw").glob("*.webm"))
shutil.move(str(raw), str(S / "tour.webm"))
(S / "marks.txt").write_text("\n".join(f"{t}\t{n}" for t, n in marks) + f"\n{total}\tend\n")
log(f"recorded {total}s -> tour.webm")

subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(S / "tour.webm"), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", "30", "-an", str(S / "tour.mp4")], check=True)
print(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "default=nw=1", str(S / "tour.mp4")], capture_output=True, text=True).stdout)

# Stills from the finished recording, at each still-mark.
shots = S / "shots"; shutil.rmtree(shots, ignore_errors=True); shots.mkdir()
for t, n in marks:
    if n.startswith("still:"):
        name = n.split("still:")[1]
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t + 0.8:.2f}", "-i", str(S / "tour.mp4"), "-frames:v", "1", str(shots / f"{name}.png")])
print("stills:", sorted(p.name for p in shots.glob("*.png")))
