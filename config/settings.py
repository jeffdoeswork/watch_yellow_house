"""Django settings for Watch Yellow House."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local development values while allowing systemd/container environment
# variables to take precedence in production.
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name):
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def env_path(name, default):
    path = Path(os.getenv(name, default))
    return path if path.is_absolute() else BASE_DIR / path


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-development-only")
DEBUG = env_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "vision",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = env_path("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "login"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE")

# Long-running object-detection worker settings. Environment variables keep
# stream credentials and machine-specific tuning out of source control.
YOLO_MODEL = os.getenv("YOLO_MODEL", str(BASE_DIR / "models" / "yolo26x.pt"))
YOLO_SOURCE = os.getenv("YOLO_SOURCE")
YOLO_DEVICE = os.getenv("YOLO_DEVICE", "0")
YOLO_IMAGE_SIZE = int(os.getenv("YOLO_IMAGE_SIZE", "640"))
YOLO_CONFIDENCE = float(os.getenv("YOLO_CONFIDENCE", "0.25"))
YOLO_FRAME_STRIDE = int(os.getenv("YOLO_FRAME_STRIDE", "1"))
YOLO_QUANTIZE = os.getenv("YOLO_QUANTIZE", "16")
