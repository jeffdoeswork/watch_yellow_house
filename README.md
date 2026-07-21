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

## Object detection worker

The YOLO worker is a separate long-running process so the model remains loaded
in GPU memory. Run it alongside the web server:

```bash
# Terminal 1: web application
python manage.py runserver

# Terminal 2: persistent detector
python manage.py run-yolo --source 'rtsp://username:password@camera/live'
```

The source may be an RTSP/RTMP/TCP/HTTP stream, a video or image path, or a
webcam index such as `0`. Instead of passing it on the command line, set
`YOLO_SOURCE` in the process environment. See `.env.example` for all tuning
settings. Environment files are not loaded automatically.

Use `--once` to process one frame and exit during setup:

```bash
python manage.py run-yolo --source path/to/test-image.jpg --once
```

The default model is `models/yolo26x.pt`, device is GPU `0`, image size is 640,
and FP16 inference is enabled. Model weights are downloaded by Ultralytics on
first use and excluded from Git.
