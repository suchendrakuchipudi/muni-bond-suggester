# Treasury Data Engine

This project provides a FastAPI backend that stores Treasury yield data in PostgreSQL and serves a simple dashboard page.

## Requirements


## Environment setup

Set the API key before running the server:

```bash
export FRED_API_KEY=your_fred_api_key
```

If you want to override the database connection, you can also set:

```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/treasury_engine
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run the server

```bash
uvicorn treasury_data_engine:app --reload
```

Then open:


## API endpoints


## GitHub Pages (Jekyll)

This repository is set up to publish via GitHub Pages using Jekyll. The site uses a custom layout at `_layouts/default.html` and the top-level `index.html` contains the page content with Jekyll front matter.

To publish on GitHub Pages:

1. Push this repository to GitHub.
2. In the repository Settings -> Pages, select the branch `main` (or `master`) and the root folder as the source.
3. The site will be available at `https://<your-username>.github.io/<repo-name>/` (or at a custom domain if configured).

If you want to use the default GitHub Pages theme instead, add a `theme:` entry to `_config.yml`.

## Run tests automatically on changes

Install development requirements and run the watcher which will re-run `pytest` whenever tracked files change:

```bash
python -m pip install -r requirements-dev.txt
./scripts/watch-tests.sh
```

The watcher runs an initial test run and then re-runs when files (Python, HTML, Markdown, YAML, JSON) are created, modified, moved, or deleted.
