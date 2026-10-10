from django.utils.html import strip_tags


def clean_text(value):
    """Remove HTML tags and surrounding whitespace from untrusted text."""
    return strip_tags(value).strip()
