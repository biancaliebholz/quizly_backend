"""Gunicorn settings for production (loaded automatically from /app).

Defaults are conservative for a shared VPS: one worker process keeps a
single Whisper/torch copy in RAM, its threads keep the API responsive
while a quiz is generated (transcriptions are serialized by a lock).
Every value can be changed with an environment variable.
"""

import os

bind = '0.0.0.0:8000'
workers = int(os.environ.get('GUNICORN_WORKERS', '1'))
threads = int(os.environ.get('GUNICORN_THREADS', '4'))
# Quiz generation runs synchronously (download, Whisper, Gemini).
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '600'))
graceful_timeout = 30
accesslog = '-'
