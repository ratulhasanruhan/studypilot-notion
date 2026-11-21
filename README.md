# StudyPilot 🧭

**Your student life on autopilot, inside Notion Student OS.** Paste a syllabus and StudyPilot plans your study time. Tell it what you enjoy (hiking, running a half marathon, sci-fi books, guitar, friends) and it suggests activities that fit your workload, schedules them around your study blocks, and scales them down in exam weeks.

Built for the **Cognition × Notion Student OS Hackathon**, end to end with Devin.

![StudyPilot web app](docs/screenshot.png)

## The problem

Every semester starts the same way: five syllabi, fifty deadlines, and an empty planner. Students copy dates into Notion by hand (or don't), then discover the midterm three days out. Knowing *when* things are due is not the same as knowing *when to work on them*.

And when the semester gets busy, everything else goes first: the run, the hike, the novel on the nightstand, time with friends. Most planners only track coursework, so the things that keep students healthy and happy never get a slot.

## What StudyPilot does

| Step | What happens in Notion |
|---|---|
| **1. Connect** | Creates four linked databases under any page you choose: **Courses**, **Assignments & Exams**, **Life Goals**, and a **Schedule** that holds study blocks and life activities (`Kind` = Study / Life). Older setups are upgraded automatically. |
| **2. Import a syllabus** | Paste any syllabus text. StudyPilot finds every dated deadline (`Sep 15`, `9/26`, `2026-10-14`, `Friday, September 18`, `3rd December`…), classifies it (Exam, Project, Quiz, Lab, Reading, Assignment), estimates effort, links it to its course, and skips duplicates on re-import. |
| **3. Autopilot plan** | Schedules study blocks before each deadline: earliest deadline first, spread across the least-loaded days in a per-type lead window (exams 10 days, projects 14…), never exceeding your daily hours cap. Deadlines that can't fit are flagged **at risk**. Re-plan anytime: sessions you tick **Done** count as progress, and future unfinished ones are rescheduled. |
| **4. Life beyond study** | Enter your interests. StudyPilot suggests activities from 18 templates (half-marathon training, Couch to 5K, weekend hikes, read for fun with a book list, gym, mindfulness, music, language, friends & clubs, volunteering…), sized to next week's study load. Add one and it becomes a **Life Goal** in Notion. The planner then puts its sessions in free morning/afternoon/evening slots that don't clash with study. Plans progress (the Saturday long run grows 1.5 km a week). In exam or heavy weeks each goal runs about half as often and long activities shrink (a hike becomes a 1.5 h nature walk). Pause, resume or finish goals at any time. |
| **5. Weekly digest** | Publishes a "Week of …" Notion page: due this week (as to-dos), overdue items, study hours per day, at-risk warnings, this week's life activities (as to-dos), and how many you completed last week. |

Everything lives in normal Notion databases, so it works with Notion's calendar, board and timeline views, and with the rest of your Student OS.

## Quick start

```bash
git clone https://github.com/ratulhasanruhan/studypilot-notion && cd studypilot-notion
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

### Try it without Notion (demo mode)

```bash
STUDYPILOT_DEMO=1 studypilot serve      # http://127.0.0.1:8000
```

### Connect your Notion

1. Go to <https://www.notion.so/profile/integrations> → **New integration** (Internal) → copy the secret.
2. In Notion, open the page that should hold your Student OS → **•••** → **Connections** → add your integration.
3. Run:

```bash
export NOTION_TOKEN=ntn_...
studypilot serve                        # web app
# or the CLI:
studypilot setup "https://www.notion.so/.../Student-OS-<id>" --timezone Asia/Dhaka
studypilot import examples/cs101_syllabus.txt --year 2026
studypilot suggest "hiking, half marathon, sci-fi books"
studypilot goal add hiking
studypilot goal add reading --target "Project Hail Mary - Andy Weir"
studypilot goal add half-marathon --days Tue,Thu,Sat
studypilot goals                        # list; `goal pause|resume|done <name>`
studypilot plan                         # writes study blocks + life activities to Schedule
studypilot digest                       # publishes this week's digest page
```

Every command takes `--dry-run`. `plan` and `digest` take `--today YYYY-MM-DD` for demos.

## How it works

```
syllabus text ──► syllabus.py (regex date finder + dateutil + keyword classifier)
                       │ Items
                       ▼
                 core.py ──► Notion API (Courses / Assignments & Exams / Life Goals / Schedule)
                       │ Items + Goals from Notion, Done hours
                       ▼
                 planner.py (EDF, load-balanced, daily cap) ──► study blocks
                 life.py (interest matching, free-slot scheduling, light exam weeks) ──► life activities ──► Schedule
                       ▼
                 digest.py ──► "Week of …" Notion page
```

| File | Purpose |
|---|---|
| `studypilot/syllabus.py` | Deadline extraction and classification |
| `studypilot/planner.py` | Study-session scheduler |
| `studypilot/life.py` | Activity templates, suggestions, life scheduling around study |
| `studypilot/digest.py` | Weekly digest + Notion block rendering |
| `studypilot/core.py` | Orchestration, idempotent import, re-planning |
| `studypilot/notion.py` | Small Notion REST client with retry on rate limits |
| `studypilot/web.py`, `static/index.html` | FastAPI app + single-page UI |
| `studypilot/fake_notion.py` | In-memory Notion for tests and demo mode |

Config (database IDs, timezone, daily cap) is saved to `.studypilot.json`.

## Tests

```bash
pytest
```

CI runs the suite on Python 3.10 and 3.12.

## Example run (live Notion workspace)

Two sample syllabi in [`examples/`](examples) plus four life goals, run on a real Student OS page on Nov 21, 2026:

```text
$ studypilot import examples/cse220_data_structures.txt --year 2026   # Created 8
$ studypilot import examples/mat216_linear_algebra.txt --year 2026    # Created 6
$ studypilot suggest "hiking, run a half marathon, sci-fi books, hang out with friends"
🏃 Half-marathon training  [half-marathon]  3x/week, 2.25h  Morning Tue/Thu/Sat
🥾 Weekend hikes  [hiking]  1x/week, 3.5h  Morning Sat/Sun
📖 Read for fun  [reading]  5x/week, 2.5h  Evening Mon/Tue/Wed/Thu/Sun
    Books: Project Hail Mary - Andy Weir; Dune - Frank Herbert; The Martian - Andy Weir; ...
🤝 Friends & clubs  [friends]  1x/week, 2.0h  Evening Fri
🧘 Mindfulness  [meditation]  5x/week, 1.25h  Morning Mon/Tue/Wed/Thu/Fri
$ studypilot goal add hiking && studypilot goal add half-marathon && \
  studypilot goal add reading --target "Project Hail Mary - Andy Weir" && studypilot goal add meditation
$ studypilot plan                     # study blocks + life activities written to Schedule
$ studypilot digest
# Week of Nov 21, 2026
## Due this week
- Tue Nov 24 - Read Chapter 9 (Heaps) (Reading, CSE 220)
- Wed Nov 25 - Problem Set 7 (eigenvalues) (Assignment, MAT 216)
## Study plan (12.5h)
- Sat Nov 21: 2.5h ... Fri Nov 27: 1.5h
## Life beyond study
- Mon Nov 23 07:00 - 🧘 Meditate 15 min
- Tue Nov 24 07:15 - 🏃 Easy run: 4.5 km
- Tue Nov 24 21:00 - 📖 Read: Project Hail Mary - Andy Weir (30 min)
...
```

## Built with Devin

StudyPilot was designed, coded, tested and connected to a live Notion workspace by Devin (Cognition) from a single chat request. See [SUBMISSION.md](SUBMISSION.md) for the hackathon write-up.

## License

MIT
