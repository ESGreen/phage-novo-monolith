"""Django settings for The Phage website."""

from __future__ import annotations

import os
from pathlib import Path

from .config import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG = load_config()

SECRET_KEY = CONFIG.site.secret_key
DEBUG = CONFIG.site.debug
ALLOWED_HOSTS = list(CONFIG.site.allowed_hosts)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "adminui",
    "camp",
    "content",
    "core",
    "payments",
    "surveys",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "thephage.urls"

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
                "content.context_processors.root_menu",
            ],
        },
    }
]

WSGI_APPLICATION = "thephage.wsgi.application"

if os.environ.get("THEPHAGE_SQLITE_PATH"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ["THEPHAGE_SQLITE_PATH"],
        }
    }
elif os.environ.get("THEPHAGE_TEST_DATABASE") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": CONFIG.database.host,
            "PORT": CONFIG.database.port,
            "NAME": CONFIG.database.name,
            "USER": CONFIG.database.user,
            "PASSWORD": CONFIG.database.password,
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "accounts.password_validation.TwoCharacterClassValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = CONFIG.site.timezone
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = CONFIG.paths.static_root
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = CONFIG.paths.media_root
PUBLIC_ROOT = CONFIG.paths.public_root
TMP_ROOT = CONFIG.paths.tmp_root

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/public/"

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
