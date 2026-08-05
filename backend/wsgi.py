"""
WSGI entry point for gunicorn: `gunicorn backend.wsgi:app`.

Run with a single worker and multiple threads. The conversation checkpointer
is in-memory, so several worker processes would each hold a different slice of
the thread history.
"""

from backend.app import create_app

app = create_app()
