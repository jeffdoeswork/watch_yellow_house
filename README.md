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

Live feeds are transcoded to browser-compatible video by FFmpeg. Install the
`ffmpeg` system package for local development; `deploy.sh` installs it in
production. The browser player includes playback, mute, and volume controls.

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

# Terminal 2: persistent shared detector for every enabled Video Feed
python manage.py run-yolo
```

Add RTSP connections under **Video feeds** in Django admin. New feeds have
detection enabled by default and can be paused with their **Detection enabled**
checkbox. With no source argument, one resident model processes enabled feeds
sequentially in round-robin order while each camera capture retains only its
newest frame. Select one record for diagnostics with `--feed-id ID`. The source
can also be overridden with `--source` or `YOLO_SOURCE`; it may be a stream,
video/image path, or webcam index such as `0`. The project `.env` file is loaded
automatically.

Use `--once` to process one frame and exit during setup:

```bash
python manage.py run-yolo --source path/to/test-image.jpg --once
```

The default model is `models/yolo26x.pt`, device is GPU `0`, image size is 640,
minimum detection confidence is 50%, and FP16 inference is enabled. Results
below the confidence threshold are excluded before they reach either the
10-frame count window or the bounding-box overlay. Model weights are downloaded
by Ultralytics on first use and excluded from Git.

For database-backed feeds, the worker publishes the latest bounding boxes and a
bounded 10-frame count history to one detection-state row per feed. The UI uses
the per-class mode of that window and keeps the previous value while modes are
tied, so displayed counts remain whole numbers without reacting to a one-frame
miss or an evenly alternating count.
`YOLO_COUNT_WINDOW` changes the window size, and
`YOLO_STATE_STALE_SECONDS` controls when old results are marked stale.

The same inference result also produces a 640-pixel-wide, quality-65 annotated
JPEG for the Dashboard once per second. Dashboard previews do not open another
RTSP connection or run another inference. Full MP4 video and audio remain on an
individual feed's detail page. Tune the independent detection and preview rates
with `YOLO_INFERENCE_FPS` and `YOLO_PREVIEW_FPS`; see `.env.example` for image,
storage, and feed-refresh settings.

## Production deployment

Deployment templates live under `scripts/`. The deployment script installs a
Gunicorn-backed Django service, a separate persistent YOLO service, and an
Nginx reverse proxy. Both services are enabled at boot when the script is run.

From the project directory, deployment and later code updates use the same
command:

```bash
bash ./deploy.sh
```

The script requests `sudo` when necessary and reads Nginx hostnames from
`DJANGO_ALLOWED_HOSTS` in the project `.env`. The optional `SERVER_NAME`
environment variable can override the Nginx hostnames for a single deployment.

Every deployment securely copies the project `.env` to
`/etc/watch-yellow-house.env`, applies production-only overrides, installs
updated requirements, runs migrations and `collectstatic`, validates the
configuration, then restarts both application services and reloads Nginx.

Set `DJANGO_SESSION_COOKIE_SECURE` and `DJANGO_CSRF_COOKIE_SECURE` to `false`
when accessing Nginx directly over LAN HTTP. Once the application is used only
through HTTPS, set both values to `true` and redeploy.

The included Nginx configuration serves HTTP. Add a TLS certificate before
exposing the login or credential-bearing application outside a trusted network.
