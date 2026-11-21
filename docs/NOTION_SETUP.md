# Notion setup and CLI

## Connect a workspace

1. Create an internal integration in Notion and copy its secret.
2. Open the page where StudyPilot should add its databases, use **••• → Connections** to share it with the integration, and grant edit access.
3. Set the integration secret and create the databases under that page:

   ```bash
   export NOTION_TOKEN="secret_..."
   studypilot setup "https://www.notion.so/your-workspace/your-page-id" --timezone "America/New_York"
   ```

Set `STUDYPILOT_CONFIG` if you want to choose where the local config is stored. `STUDYPILOT_APP_URL` optionally adds a Web app link to the dashboard. Do not commit tokens or config files containing credentials.

## Commands

Run these from the repository root after installing the package with `pip install -e ".[dev]"`.

```bash
# Parse a syllabus file and import its deadlines (course and year can be supplied).
studypilot import syllabus.txt --course "CS 101" --year 2026

# Get life-activity suggestions based on interests.
studypilot suggest "hiking, running, sci-fi books"

# Add a goal using a template key, optionally customizing its target and schedule.
studypilot goal add hiking --target "local trails" --per-week 1 --hours 2 --days Sat --time Morning

# Preview with --dry-run, or write a fresh plan to Notion.
studypilot plan --today 2026-09-01

# Refresh the dashboard on the configured parent page.
studypilot dashboard --today 2026-09-01

# Publish the weekly summary as a separate page under the parent page.
studypilot digest --today 2026-09-01

# Choose a free micro-adventure; --add writes it to Schedule.
studypilot surprise --interests "hiking, photography" --add --today 2026-09-01
```

## Dashboard refresh

StudyPilot stores the IDs of the dashboard blocks it created. The next refresh archives only those blocks, then inserts the replacement dashboard; it does not replace other content on the parent page or replan Schedule. By default it appends at the end of the page. Use `--after BLOCK_ID` to insert it immediately after a chosen block, for example:

```bash
studypilot dashboard --after 0123456789abcdef0123456789abcdef
```

The anchor is saved in the local config. Passing `--after top` or an empty anchor appends the dashboard at the end.
