"""Read typed settings from environment variables (loaded from .env)."""

import os

TRUE_VALUES = {'1', 'true', 'yes', 'on'}


def env_bool(name, default=False):
    """Return True for '1', 'true', 'yes' or 'on' (case-insensitive)."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def env_list(name, default=''):
    """Return a comma-separated variable as a list without blank entries."""
    raw_value = os.environ.get(name, default)
    return [item.strip() for item in raw_value.split(',') if item.strip()]
