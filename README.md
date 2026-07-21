# Watch Yellow House

A responsive Django starter project with a shared vertical navigation shell.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

Local settings are loaded from `.env`. Real process environment variables take
precedence, so production values supplied by systemd are not overwritten by a
project-level file. At minimum, review `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
`DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` before deployment.

The application has no registration page. Sign in with a Django user at
`/login/`; administrators can manage RTSP connections at `/admin/` under
**Video feeds**. Authenticated users can browse feeds at `/video-feeds/` and
open an individual player at `/video-feeds/<id>/`.

## Project layout

- `config/` — project-level settings and URL configuration
- `core/` — the first site app and its page routes
- `templates/` — shared layouts, components, and app templates
- `static/` — styles and small interactive behaviors

New pages should extend `base.html`; the shared sidebar is rendered from
`templates/components/sidebar.html`.

## Object detection worker

The YOLO worker is a separate long-running process so the model remains loaded
in GPU memory. Run it alongside the web server:

```bash
# Terminal 1: web application
python manage.py runserver

# Terminal 2: persistent detector using the first saved Video Feed
python manage.py run-yolo
```

Add RTSP connections under **Video feeds** in Django admin. With no source
argument, the worker uses the first saved feed. Select a specific record with
`--feed-id ID`. The source can also be overridden with `--source` or the
`YOLO_SOURCE` environment variable; it may be a stream, video/image path, or a
webcam index such as `0`. See `.env.example` for all tuning settings.
Environment files are not loaded automatically.

Use `--once` to process one frame and exit during setup:

```bash
python manage.py run-yolo --source path/to/test-image.jpg --once
```

The default model is `models/yolo26x.pt`, device is GPU `0`, image size is 640,
and FP16 inference is enabled. Model weights are downloaded by Ultralytics on
first use and excluded from Git.

## Production deployment

Deployment templates live under `scripts/`. The deployment script installs a
Gunicorn-backed Django service, a separate persistent YOLO service, and an
Nginx reverse proxy. Both services are enabled at boot when the script is run.

From the project directory, deployment and later code updates use the same
command:

```bash
bash ./deploy.sh
```

The script requests `sudo` when necessary. On first deployment it detects the
machine hostname and IPv4 addresses; later deployments reuse the hosts from
`/etc/watch-yellow-house.env`. To use a specific domain on the first run, the
optional form is `SERVER_NAME=watch.example.com bash ./deploy.sh`.

The environment file is created once and preserved on later deployments. Edit
it for environment-specific Django or YOLO settings. Every deployment installs
updated requirements, runs migrations and `collectstatic`, validates the
configuration, then restarts both application services and reloads Nginx.

The included Nginx configuration serves HTTP. Add a TLS certificate before
exposing the login or credential-bearing application outside a trusted network.
