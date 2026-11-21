# Architecture

## Module map

| File | Responsibility |
|---|---|
| `api/index.py` | Vercel ASGI entry point; restores the original URL path from the rewrite query parameter and enables demo defaults. |
| `studypilot/__init__.py` | Package version. |
| `studypilot/__main__.py` | Runs the command-line interface as `python -m studypilot`. |
| `studypilot/balance.py` | Calculates weekly Balance Scores, labels, and tips. |
| `studypilot/charts.py` | Builds compact QuickChart URLs for dashboard charts. |
| `studypilot/cli.py` | Implements the `studypilot` command-line interface. |
| `studypilot/core.py` | Coordinates Notion setup, imports, planning, goals, dashboards, digests, and autopilot. |
| `studypilot/dashboard.py` | Builds the Notion dashboard blocks from a plan and current data. |
| `studypilot/digest.py` | Builds the weekly digest model and its Notion blocks. |
| `studypilot/fake_notion.py` | In-memory Notion-compatible client for tests and web demo mode. |
| `studypilot/life.py` | Life-goal templates, interest matching, life scheduling, and micro-adventures. |
| `studypilot/models.py` | Planner data models and deadline lead-window defaults. |
| `studypilot/notion.py` | Notion API client and block/page/database operations. |
| `studypilot/planner.py` | Earliest-deadline-first study-session planner. |
| `studypilot/schema.py` | Notion database property definitions. |
| `studypilot/static/index.html` | The single-page browser application. |
| `studypilot/syllabus.py` | Extracts deadline items from syllabus text. |
| `studypilot/web.py` | FastAPI routes and web-app demo initialization. |

## Data flow

Syllabus text is parsed into deadline `Item`s, then imported into the Assignments & Exams database and linked to a Course. Imports deduplicate matching items. Planning reads pending items and completed study hours, schedules sessions, and writes the resulting study and life sessions to Schedule. Replanning archives only future, unfinished rows marked `Planned by: StudyPilot`; manually added and Surprise rows are left alone.

Active Life Goals are scheduled around study load in Morning, Afternoon, or Evening slots. Weeks containing an exam or a heavy study load are treated as light weeks: goal frequency is reduced and long activities are shortened. The weekly Balance Score summarizes the resulting study/life plan. The dashboard uses a preview of that plan and does not replan or write Schedule sessions. A digest builds a weekly summary and, when published, creates a separate page under the parent page.

## Notion databases

The current setup provisions **four** databases (not five): Courses, Assignments & Exams, Schedule, and Life Goals. The Schedule database gains its `Kind` and `Goal` properties when Life Goals is enabled.

| Database | Properties |
|---|---|
| Courses | `Name` (title), `Code` (rich text). |
| Assignments & Exams | `Name` (title), `Course` (relation to Courses), `Type` (select: Assignment, Exam, Quiz, Project, Lab, Reading), `Due` (date), `Status` (select: Not started, In progress, Done), `Est. Hours` (number), `Source` (select: Syllabus, Manual). |
| Schedule | `Name` (title), `Assignment` (relation to Assignments & Exams), `When` (date), `Hours` (number), `Done` (checkbox), `Planned by` (select: StudyPilot, Surprise, Me), `Kind` (select: Study, Life), `Goal` (relation to Life Goals). |
| Life Goals | `Name` (title), `Category` (select: Fitness, Outdoors, Reading, Creative, Social, Wellbeing, Skill), `Template` (rich text), `Sessions/Week` (number), `Hours/Session` (number), `Days` (multi-select: Mon–Sun), `Time` (select: Morning, Afternoon, Evening), `Status` (select: Active, Paused, Done), `Target` (rich text), `Started` (date). |

## Planning and Balance Score

The study planner orders unfinished, future-due items by earliest deadline (larger estimates break ties). It places work in each item's lead window—Exam 10 days, Project 14, Assignment 6, Lab 4, Quiz 4, Reading 3, or 5 days by default—on the least-loaded available day, preferring later days on ties. Defaults are a 3-hour daily cap, 1.5-hour blocks, a 0.5-hour minimum block, and an 18:00 study start. Work that cannot fit is reported as at risk.

For each seven-day week, the Balance Score starts at 100:

- If study load exceeds half of available daily capacity, subtract `(load - 0.5) × 80`.
- If there is study and life is less than 20% of planned study-plus-life hours, subtract `(0.2 - life_share) × 150`.
- Subtract 10 for each at-risk deadline, up to three; subtract another 10 if there is no study-free day.
- Subtract 10 if there is an exam and no life activity planned.
- Round and clamp the result to 0–100. Scores of 75–100 are **Balanced**, 50–74 **Stretched**, and below 50 **Burnout risk**.

## Demo mode

The web app uses `FakeNotion` when `STUDYPILOT_DEMO` is set or `NOTION_TOKEN` is absent. On a fresh demo instance, middleware bootstraps demo databases before handling a request other than `/api/setup`. The fake client is in-memory; it is intended for demos and tests, not durable storage. The command-line interface connects to Notion and requires a token.
