"""WSGI config for thephage."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thephage.settings")

application = get_wsgi_application()
