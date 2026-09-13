# From a fresh clone to a recorded demo

[DEMO.md](DEMO.md) is what to *say*. This is what to *do* — every command and
every credential, in the order that gets you to a machine worth pointing a
screen recorder at.

Budget: **45 minutes** the first time, of which about 20 is waiting on Google.
If you only have 15 minutes, do Part 1 and Part 3 — Telegram plus Notion is
enough for a demo that reads as real, and you can narrate the rest.

---

## Part 0 — Open the project (5 min)

```bash
cd ~/Downloads/Handoff/Handoff       # the inner directory is the project
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,groq,web,calendar]"
```

Prove it works before touching a single credential:

```bash
make demo        # the whole loop, scripted model, no keys, no network
make test        # 313 tests
```

If `make demo` prints a run that handled some items and set others aside, the
project is healthy and everything below is just connecting it to real accounts.

Now copy the config template:

```bash
cp .env.example .env
```

Open `.env` in your editor. **Everything below goes in this one file.** It is
gitignored — `scripts/check_secrets.sh` runs in CI to make sure it stays that
way.

---

## Part 1 — A real brain (5 min, free)

The agent needs a model. Groq's free tier is the fastest path and also serves
the speech models, so voice works without an AWS account.

1. <https://console.groq.com/keys> → **Create API Key** → copy it
2. In `.env`:

```bash
HANDOFF_MODEL_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

3. Verify — this makes a real call, it does not just check the variable is set:

```bash
handoff doctor groq
```

You want `PASS`. If you have AWS Bedrock access instead, use
`HANDOFF_MODEL_PROVIDER=bedrock` and see [SETUP.md](SETUP.md) Step 1 Option C.

---

## Part 2 — Telegram (5 min, free) — **record this one**

This is the shot. A decision the agent cannot make arrives on your phone as a
message with buttons, you tap one, and the run resumes on screen.

1. Open Telegram. Search **@BotFather**. Send `/newbot`.
2. Answer the two questions (a display name, then a username ending in `bot`).
3. Copy the token it gives you — `123456789:AAE...`
4. In `.env`:

```bash
TELEGRAM_BOT_TOKEN=123456789:AAE...
```

5. **Open a chat with your new bot and send it "hi".** A bot cannot start a
   conversation with you; this is the step that lets it reply.
6. Ask Handoff to find your chat id:

```bash
handoff doctor telegram
```

It reads the message you just sent and prints the exact line to paste:

```
SKIP  Telegram   token works; set TELEGRAM_CHAT_ID=987654321
```

7. Paste that into `.env`, then run it again:

```bash
handoff doctor telegram          # PASS — and your phone buzzes
```

8. Finally, route waiting decisions there. In `.env`:

```bash
NOTIFY_CHANNEL=telegram
```

---

## Part 3 — Notion (5 min, free)

Where the run writes itself up — the artefact you show at the end of the video.

1. <https://www.notion.so/my-integrations> → **New integration** → name it
   `Handoff` → **Save** → copy the **Internal Integration Secret** (`ntn_...`)
2. In Notion, create a **database** (a full-page table) called *Handoff runs*.
3. **Share it with the integration.** Open the database → **`...`** (top
   right) → **Connections** → **Connect to** → `Handoff`.

   > Do not skip this. The integration can only see pages it was invited to.
   > Without it, a perfectly valid key returns *"Could not find page"* — this
   > is the single most common setup failure, and `handoff doctor notion` will
   > tell you so in as many words.

4. Copy the database id out of the URL. In
   `notion.so/myspace/**1a2b3c4d5e6f...**?v=...` it is the 32 characters
   between the last `/` and the `?`.
5. In `.env`:

```bash
NOTION_API_KEY=ntn_...
NOTION_DATABASE_ID=1a2b3c4d5e6f...
```

6. Verify — this checks the key *and* that the database is reachable, because
   the first can pass while the second fails:

```bash
handoff doctor notion
```

---

## Part 4 — Airtable (10 min, free)

The decision log. This is what makes "the gate is well calibrated" a table
rather than a claim, and it is the thing to point at when anyone asks how you
know it works.

1. <https://airtable.com> → create a base → rename the default table to
   **Decisions**.
2. Give it exactly these fields (delete Airtable's default ones):

   | Field | Type |
   |---|---|
   | `Item` | Single line text |
   | `Action` | Single line text |
   | `Confidence` | Number, 3 decimal places |
   | `Decided by` | Single line text |
   | `Reasoning` | Long text |
   | `Workflow` | Single line text |
   | `Run` | Single line text |
   | `At` | Single line text |

3. <https://airtable.com/create/tokens> → **Create token** → scopes
   `data.records:write` and `schema.bases:read` → **Add a base** → pick yours.
4. The base id is the `app...` in the base's URL.
5. In `.env`:

```bash
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...
AIRTABLE_TABLE=Decisions
```

6. Verify — it names any column you got wrong:

```bash
handoff doctor airtable
```

A missing column costs that one value, not the run: unknown fields are dropped
against the live schema before writing.

---

## Part 5 — Gmail and Google Calendar (20 min, free)

The longest part, because Google requires a Cloud project. **Both services
share one project and one downloaded file** — do Gmail first, then Calendar is
three extra clicks.

### The Google project (once)

1. <https://console.cloud.google.com> → **New Project** → call it `Handoff`
2. **APIs & Services → Library** → enable **Gmail API**
3. Same Library → enable **Google Calendar API**
4. **APIs & Services → OAuth consent screen** → External → fill the required
   fields → under **Audience → Test users**, add your own Gmail address
5. **Data access → Add or remove scopes** → add both:
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/calendar.events`
6. **Credentials → Create credentials → OAuth client ID → Desktop app** →
   **Download JSON**
7. Save that file as:

```bash
mkdir -p ~/.gmail-mcp
mv ~/Downloads/client_secret_*.json ~/.gmail-mcp/gcp-oauth.keys.json
```

### Gmail

```bash
handoff credentials gmail     # opens the browser, consent once
handoff doctor gmail          # PASS — reports how many tools came back live
```

Handoff asks for `gmail.modify`: read, archive, label, draft. **It cannot send
mail.** Worth saying out loud in the video.

### Google Calendar

```bash
handoff credentials gcal      # same file, different scope
handoff doctor gcal           # PASS — prints your calendar and timezone
```

### Linear (optional, 2 min)

If you want tickets to be real rather than narrated:

1. Linear → **Settings → API → Personal API keys** → create one
2. `LINEAR_API_KEY=lin_api_...` in `.env`
3. `handoff doctor linear`

---

## Part 6 — Go live and check everything (2 min)

One switch turns off the synthetic inbox:

```bash
USE_MOCK_TOOLS=false
```

> **Narrow the mail query first.** The template fetches
> `is:unread newer_than:16h`. Against a real mailbox, edit
> `src/handoff/workflows/morning_ops.json` to `newer_than:2h` for the first
> run. The gate protects you from *wrong* actions, not from *many* actions.

Then the full sweep — every check makes a real call:

```bash
handoff doctor
```

This is a good shot for the video: a column of `PASS` is the reliability
evidence, and it is honest, because `SKIP` means *not configured* and `FAIL`
always comes with the fix.

---

## Part 7 — Record it (the two-minute cut)

Set up three things on screen before you hit record:

| Pane | Command | Why |
|---|---|---|
| Browser | `handoff serve` → <http://localhost:8000> | The run graph drawing itself |
| Terminal A | `handoff answers listen` | Takes the taps from your phone |
| Phone | Your Telegram chat, screen-mirrored or filmed | The moment worth watching |

Then:

```bash
# Terminal B
handoff workflows show morning-ops-run     # 10s: six apps, one workflow
handoff run morning-ops-run                # the run
```

### The 2:00 cut

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | `handoff workflows show morning-ops-run` | "One workflow. Gmail, Calendar, Linear, Notion, Airtable, Telegram." |
| 0:15–0:45 | The run graph filling in | "It reads the mail and my calendar, files the real asks in Linear, and books time to actually do them." |
| 0:45–1:10 | **Phone buzzes, buttons visible** | "It hit one it can't call. It doesn't guess — it asks, once, for the whole batch." |
| 1:10–1:25 | **Tap a button; the run resumes on screen** | "One tap. Same code path as the browser. The run finishes." |
| 1:25–1:45 | The Notion page, then the Airtable table | "Written up in Notion. And every decision logged with the confidence it had — which is how I know the gate is calibrated, not just asserted." |
| 1:45–2:00 | `handoff rules` | "My answer became a rule. Tomorrow it asks about one thing fewer." |

### Practical notes

- **Rehearse on the scripted model.** `HANDOFF_FAKE_MODEL=true handoff run
  morning-ops-run` is instant and free. Run it until the beats land, then
  switch back for the real take.
- **Record at 1080p minimum.** OBS Studio is free and handles a webcam-free
  screen capture fine.
- **Don't rush the phone moment.** It is the whole argument of the project;
  give it four seconds of silence.
- **Record the voiceover separately** in a quiet room and lay it over the
  capture. Live narration while typing always sounds rushed.
- If a live service misbehaves mid-take, `USE_MOCK_TOOLS=true` gives you a
  deterministic eight-message inbox that always produces one escalation.

---

## If something is red

| Symptom | Cause | Fix |
|---|---|---|
| Notion: *"Could not find page"* | The integration was never invited | Database → `...` → Connections → add it |
| Telegram: *"chat not found"* | You never messaged the bot | Send it "hi", then `handoff doctor telegram` |
| Telegram: taps do nothing | No listener running | `handoff answers listen` in its own pane |
| Airtable: `NOT_FOUND` | Token has no access to that base | Re-create the token, **Add a base** |
| Calendar: *"not signed in"* | Consent never completed | `handoff credentials gcal` |
| Gmail: `npx not found` | Node.js missing | Install Node, then `handoff credentials gmail` |
| Any: `invalid_grant` | You are not a test user on the consent screen | Add your address under **Audience → Test users** |

`handoff doctor <name>` re-runs one check on its own — `groq`, `anthropic`,
`bedrock`, `speech`, `gmail`, `linear`, `slack`, `github`, `notion`,
`telegram`, `airtable`, `gcal`, `dynamodb`, `memory`.
