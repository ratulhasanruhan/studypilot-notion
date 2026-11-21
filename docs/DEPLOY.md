# Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fratulhasanruhan%2Fstudypilot-notion)

The project includes the Vercel configuration in [`vercel.json`](../vercel.json) and the Python function entry point in [`api/index.py`](../api/index.py). The rewrite sends each incoming path to `/api/index?__path=$1`. Vercel invokes the function at `/api/index` rather than preserving the original URL path, so `api/index.py` restores it from `__path` before handing the request to FastAPI. The function configuration includes `studypilot/**` so the Python package and `static/index.html` are bundled.

## Demo and workspace modes

Without `NOTION_TOKEN`, the entry point enables demo mode. The web app uses an in-memory `FakeNotion` workspace and bootstraps it automatically on the first request other than `/api/setup`, so a fresh demo can be used without connecting Notion. Demo data is not durable across serverless instances.

To connect a workspace, add `NOTION_TOKEN` to the Vercel project's environment variables and share the target Notion page with that integration. Set `STUDYPILOT_APP_URL` if you want the Notion dashboard to link back to the deployed app. The function defaults `STUDYPILOT_CONFIG` to `/tmp/studypilot.json`; Vercel's temporary filesystem is instance-local and should not be treated as persistent storage.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
STUDYPILOT_DEMO=1 uvicorn api.index:app --port 8000 --reload
```

Open <http://127.0.0.1:8000>. To use a Notion workspace locally, set `NOTION_TOKEN` and configure it through the app or CLI.
