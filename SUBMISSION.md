# StudyPilot — Cognition × Notion Student OS Hackathon submission

**One line:** Paste a syllabus; StudyPilot fills your Notion Student OS with every deadline, auto-schedules study sessions before each one, and publishes a weekly digest.

## Problem
Students get several syllabi per term with dozens of deadlines in inconsistent formats. Copying them into Notion is tedious, and a list of due dates still doesn't tell you *when to study*. The result: cramming and missed deadlines.

## Solution
StudyPilot is a web app + CLI that plugs into Notion Student OS:

1. **Connect** – creates linked *Courses*, *Assignments & Exams* and *Study Sessions* databases under any Notion page.
2. **Import a syllabus** – extracts dated deadlines from free-form text (many date formats), classifies them (Exam / Project / Quiz / Lab / Reading / Assignment), estimates hours, links the course, and de-duplicates on re-import.
3. **Autopilot plan** – earliest-deadline-first scheduler spreads study blocks across the least-loaded days before each deadline, respects a daily hours cap, and flags deadlines that can't fit as *at risk*. Re-planning keeps sessions you marked Done and reschedules the rest.
4. **Weekly digest** – publishes a Notion page with what's due this week (to-dos), overdue items, hours planned per day, and risk warnings.

## How Devin and Notion were used
- **Devin (Cognition)** built the whole project from one chat request: product plan, Python package, Notion integration, scheduler, web UI, 18 tests, docs, and the live Notion connection.
- **Notion** is the system of record: everything is regular Notion databases and pages, so calendar, board and timeline views of the Student OS work out of the box.

## Tech
Python 3.10+, FastAPI, Notion REST API (2022-06-28), python-dateutil, vanilla HTML/JS, pytest. An in-memory Notion fake powers tests and a no-token demo mode.

## Impact
- Setting up a course goes from ~30 minutes of copy-pasting to under a minute.
- Turns deadlines into a daily plan with a workload cap, which reduces last-minute cramming.
- At-risk warnings show overload weeks early, while there is still time to adjust.

## What's next
- LLM fallback for messy syllabus PDFs, and PDF upload.
- Google Calendar export of Study Sessions.
- Scheduled weekly digests (cron / Notion automations).
- Using actual time spent to improve hour estimates.

## Links
- Repo: <add GitHub URL>
- Demo video: <add link>
- Notion template / example workspace: <add link>
