# The demo video — full voiceover script (2:00)

Read this straight into a mic in a quiet room, then lay it over the screen
capture from [RECORDING.md](RECORDING.md). Don't narrate live while you type —
it always sounds rushed, and the pauses matter more than the words.

Every line has a timestamp and the exact screen it goes over. Practice it
twice out loud before recording; it reads in almost exactly two minutes at a
normal talking pace.

---

## The story this script tells

Not "here are our features." One person, one Monday, one morning — because a
judge remembers a story and forgets a feature list.

**Priya** runs engineering at a 12-person startup. Every Monday she opens her
laptop to 40 unread emails, three of them real asks, the rest noise. She
files the real ones as tickets by hand, archives the rest, drafts a reply to
her cofounder, and only then looks at her calendar to find time to actually
do any of it. Twenty-five minutes, every day, before her first coffee is
finished — and none of it is hard. It's just relentless, and it's never been
worth hiring someone or building a tool for.

The problem isn't that she needs an assistant. It's that every "AI assistant"
she's tried is one more app to open and manage — another inbox for her
attention. What she actually wants is something that does the twenty-five
minutes *without being asked*, and only interrupts her for the one email
that's genuinely a judgment call.

That's the whole pitch. Handoff is that sentence, running.

---

## 0:00 – 0:15 — The problem, cold open

**Screen:** black, then a phone lock screen with 40 unread mail notifications
stacking up. Cut to a tired hand reaching for coffee.

> "Priya runs engineering at a 12-person startup. Every Monday, before her
> coffee's even done, she loses twenty-five minutes to the same three things:
> file the real asks, archive the noise, reply to her cofounder. It's never
> hard. It's just every single morning."

## 0:15 – 0:30 — What's different, said plainly

**Screen:** cut to `handoff workflows show morning-ops-run` in a terminal.

> "Most tools that promise to help are just another app to open and manage.
> Handoff isn't. You describe the job once, in a sentence — it runs by
> itself, across six real apps, and it only comes back to you for the one
> decision that's genuinely unclear."

## 0:30 – 1:00 — Watch it actually run

**Screen:** browser on `handoff serve`, the run graph filling in node by node
as `handoff run morning-ops-run` executes in the terminal beside it.

> "Eight o'clock, nobody's watching. It reads her mail and her calendar
> together — not one after the other, together, because a ticket with no
> time booked for it is just a wish. The real ask from a teammate becomes a
> Linear ticket. It books her the next free half hour to actually do it. The
> newsletter gets archived. The draft to her cofounder writes itself."

## 1:00 – 1:25 — The moment that matters: it asks

**Screen:** phone, screen-recorded or filmed, buzzing with a Telegram message
and three tappable buttons. Hold on this for a real four seconds of silence
before continuing.

> "Then it hits one it genuinely can't call — a vendor pitching a
>'partnership,' real stakes, unclear intent. It doesn't guess. It doesn't
> ask about every email either — that's just a worse inbox. It stops, once,
> for the whole batch, and puts the real decision on her phone with the
> actual answers as buttons."

**Screen:** the tap; the run resuming live on the browser behind it.

> "One tap. Same code path as the browser decision screen — it makes no
> difference which one she used. The run finishes itself."

## 1:25 – 1:45 — The proof, not just the promise

**Screen:** cut to the Notion page the run wrote, then the Airtable log with
its confidence column visible.

> "Every run writes itself up in Notion. And every decision — the ones it
> made alone and the one she made for it — gets logged to Airtable with the
> confidence it had at the time. That's not a screenshot I'm asking you to
> trust. That's a table anyone can audit for how often it asks, and whether
> it was right when it didn't."

## 1:45 – 2:00 — Why it won't ask again, and the close

**Screen:** `handoff rules` in the terminal, then the header poster / logo.

> "Her answer just became a rule. Next Monday, it asks about one fewer thing.
> The week after, fewer still. It doesn't get smarter by watching her more
> closely — it gets quieter, because that was always the actual ask: not an
> agent that does everything, one that knows the difference between what it
> can decide and what it can't. Handoff. Describe it. Hand it off. It runs."

---

## Why this is the one to lead with (say this if a judge asks, not on camera)

Three things nobody else in this space usually shows, in order of how often
they're skipped:

1. **It spans real apps, not a mocked demo.** Gmail, Google Calendar, Linear,
   Notion, Airtable, Telegram — six live services in one run, each with its
   own credential and its own `doctor` check that makes a real call. Most
   "multi-agent" demos fake at least one integration; nothing here is.

2. **The interrupt is structural, not a prompt.** The gate is a
   `BeforeToolCallEvent` hook that raises `InterruptException` *before* the
   tool body runs — the model cannot talk its way past it, because the code
   path that would send the email or file the ticket never executes below
   the confidence threshold. That's the difference between "the agent
   decided to ask" and "the agent literally could not act."

3. **The evidence is a table, not a demo reel.** The Airtable log is the
   answer to the only question that matters for an autonomous agent — *how
   often does it ask, and was it right when it didn't* — and it's checkable
   by anyone, not just believable because the video looked good.

That's the pitch in one sentence: an agent that runs autonomously across
real infrastructure, and asks exactly once, exactly when it should.
