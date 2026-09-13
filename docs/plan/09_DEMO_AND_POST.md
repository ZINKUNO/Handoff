# Handoff — Demo Video Script

---

## Part 1: Demo Video (≤5 minutes)

### Storyboard

#### 0:00–0:40 — THE PROBLEM
**Voiceover:** "Every day, professionals lose hours to the same small tasks — triaging email, filing tickets, sending follow-ups. Each one takes a few minutes, but together they drain real time and attention."

**On screen:** Quick montage of inbox, ticket boards, Slack channels — the daily grind.

**Voiceover:** "The usual fix — another app to manage — just adds overhead. What if you could describe the task once, hand it off, and it just runs?"

#### 0:40–1:10 — INTRODUCE HANDOFF
**Voiceover:** "Meet Handoff. You describe a repetitive task in plain language. Handoff builds it into an autonomous workflow that runs on schedule — and only pings you when there's a real decision to make."

**On screen:** Show the Handoff dashboard. Clean, professional, dark theme.

#### 1:10–2:00 — BUILD A WORKFLOW (Chat)
**Voiceover:** "Let me show you. I open the chat and type..."

**On screen:** Type into the chat interface:
> "Every weekday at 8am, triage my inbox. Real asks from teammates → file as Linear tickets. Newsletters → archive. Anything from my manager → draft a reply. Anything ambiguous → ask me."

**Voiceover:** "The Builder Agent interprets this, selects the right MCP tools — Gmail, Linear, Slack — and generates a workflow."

**On screen:** Show the Builder Agent responding with the workflow config preview.

**Voiceover:** "One conversation. The workflow is ready."

#### 2:00–3:30 — WATCH IT RUN (Autonomous Execution)
**Voiceover:** "Now let's trigger it. The workflow runs in the background on AgentCore Runtime."

**On screen:** Click "Run Now" on the dashboard. Show the trace viewer:

**Voiceover (narrate each step):**
- "It fetches 8 unread emails..."
- "Classifies each one using its judgment..."
- "Alice's API review request — clear teammate ask, confidence 95% — auto-files a Linear ticket."
- "TechCrunch newsletter — obvious, 99% confidence — auto-archived."
- "Manager's sync request — drafts a reply automatically."
- "Bob's sprint retro — another teammate ask — auto-filed."
- "GitHub security alert — auto-filed as a ticket."

**On screen:** Show the trace: 5 items handled autonomously, green checkmarks. The agent is working.

**Voiceover:** "Five items handled. Zero interruptions. The agent just did five minutes of work in seconds."

#### 3:30–4:30 — THE MONEY MOMENT (Human Decision) ⭐
**Voiceover:** "But then it hits an email from an unknown vendor — 'Partnership opportunity.' The agent isn't sure. Is this spam, or a real business lead?"

**On screen:** Trace shows a yellow "⏸️ Paused" indicator. Notification pops up:
> "🔔 Handoff needs your input"

**Voiceover:** "The agent pauses. It fires an interrupt and surfaces ONE decision."

**On screen:** Click through to the Decision Screen. Show:
- Email summary
- Agent's reasoning: "Unknown sender, could be spam or a legitimate business inquiry. Confidence: 30%."
- Confidence bar (low, visual)
- Action buttons: [Archive] [Reply] [File Ticket] [Skip]

**Voiceover:** "One screen. One decision. I click Archive."

**On screen:** Click "Archive." Screen shows ✅ "Decision applied. Workflow resumed."

**Voiceover:** "The agent archives it, logs my decision, and — here's the key — it learns. Next time it sees email from this vendor, it archives automatically. No interruption."

#### 4:30–4:50 — WHY IT MATTERS
**Voiceover:** "Handoff uses every major feature of the Strands Agents SDK: Graph orchestration for deterministic workflows, the interrupt gate for human-in-the-loop decisions, MCP for tool integration, AgentCore Memory for learning, and it's deployed on AgentCore Runtime as a serverless background job."

**On screen:** Quick flash of the architecture diagram.

**Voiceover:** "It's not another app to manage. You describe it once. You hand it off. It runs."

#### 4:50–5:00 — CLOSE
**On screen:** Handoff logo + tagline + repo URL + live demo link.

**Voiceover:** "Handoff. Built on the Strands Agents SDK. Thank you."

---

### Video Production Tips
- **Screen recording:** OBS Studio (free) or Loom.
- **Voiceover:** Record separately in a quiet room; edit over screen capture.
- **No face cam needed** — the screen is the story.
- **Resolution:** 1080p minimum.
- **Pacing:** don't rush the Decision Screen moment — that's the payoff.
- **Show the trace:** the observability trace is proof the agent is real, not scripted. Pause on it for 2-3 seconds.
- **Narrate problem/who/why explicitly** — these are the three required beats.

---
