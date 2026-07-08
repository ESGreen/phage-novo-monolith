# The Phage Website

Django replacement for `thephage.org`.

## Current State

Implementation is underway as a custom Django app. Maintainer runbooks live in `docs/`, and design/background notes live in `design_docs/`.

Start with `docs/admin-ui.md` for the current custom admin UI and `docs/yearly-rollover.md` for annual setup.

## Local Setup

Create a virtualenv and install the project with development dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"
```

Run tests:

```bash
.venv/bin/pytest
```

Run Django commands with a config file:

```bash
THEPHAGE_CONFIG=tests/fixtures/thephage.test.toml .venv/bin/python manage.py check
```

Production config lives at `/etc/thephage/thephage.toml`. The committed example is `deploy/thephage.toml.example`.
