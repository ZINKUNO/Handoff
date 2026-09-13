# The videos

Three cuts, all rendered from this repository at 1920×1080, 30 fps.

| File | Length | What it is |
|---|---|---|
| `handoff-demo-2min.mp4` | 1:54 | **The submission cut.** Priya's Monday morning, told over live footage of the app and the animated explainer. Script: [`docs/VIDEO_SCRIPT.md`](../VIDEO_SCRIPT.md). |
| `handoff-pitch.mp4` | 6:21 | The pitch deck, narrated slide by slide, with the live app cut in where the deck talks about it running. Script: [`docs/pitch/script.md`](../pitch/script.md). |
| `handoff-explainer.mp4` | 1:38 | An animated walk-through of how it works: the sentence, the run across six apps, the gate, the phone, the log, the rule. |

Only the two-minute cut is committed; the other two are large and live beside it
in a local checkout (regenerate them with the pipeline below).

## How they were made

Nothing here was filmed by hand and nothing is mocked up in an editor.

- **The app footage is the real app.** A Playwright script starts `handoff serve`
  on the scripted offline model and the synthetic inbox — the same
  `HANDOFF_FAKE_MODEL=true` mode the test suite uses — and drives it through the
  welcome wizard, a run, the three decisions that run sets aside, the learned
  rules, the credentials page and the tool catalogue, recording at 1080p. The
  offline model is what makes the take deterministic; every screen you see is
  the shipped UI doing what it does.
- **The explainer is a web page.** One HTML file with a Web Animations timeline
  that a renderer seeks frame by frame (`window.seek(t)`) and screenshots at
  30 fps; ffmpeg assembles the frames. The scene lengths come from the
  narration, not the other way round.
- **The narration is synthetic** (Microsoft Edge neural voice via `edge-tts`),
  generated from the scripts in this repo. Re-record it in your own voice
  before submitting if you can — [`docs/RECORDING.md`](../RECORDING.md) says how.
- **The deck slides** are rendered by `marp-cli` from
  [`docs/pitch/deck.md`](../pitch/deck.md); each is held for its narration with
  a slow push-in and a crossfade.
- **Captions** are burned in from the narration text, so each video reads with
  the sound off.

The pipeline scripts (`tts.py`, `capture_tour.py`, `explainer.html`,
`render_explainer.py`, `assemble_pitch.py`, `assemble_demo.py`) are plain
Python + ffmpeg and are kept in [`scripts/video/`](../../scripts/video/).
