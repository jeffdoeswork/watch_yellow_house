# Watch Yellow House

A responsive Django starter project with a shared vertical navigation shell.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

## Project layout

- `config/` — project-level settings and URL configuration
- `core/` — the first site app and its page routes
- `templates/` — shared layouts, components, and app templates
- `static/` — styles and small interactive behaviors

New pages should extend `base.html`; the shared sidebar is rendered from
`templates/components/sidebar.html`.

