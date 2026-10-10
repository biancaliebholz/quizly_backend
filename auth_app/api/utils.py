from urllib.parse import urlsplit

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.settings import api_settings


def get_url_origin(url):
    """Return the 'scheme://host[:port]' part of a URL."""
    parts = urlsplit(url)
    return f'{parts.scheme}://{parts.netloc}'


def has_origin_headers(request):
    return 'HTTP_ORIGIN' in request.META or 'HTTP_REFERER' in request.META


def get_request_origin(request):
    """Return the Origin header, falling back to the Referer's origin."""
    origin = request.META.get('HTTP_ORIGIN')
    if origin is not None:
        return origin
    referer = request.META.get('HTTP_REFERER')
    return get_url_origin(referer) if referer else None


def is_trusted_origin(request):
    return get_request_origin(request) in settings.CSRF_TRUSTED_ORIGINS


def enforce_trusted_origin(request):
    """CSRF guard: reject requests from a missing or untrusted origin (403)."""
    if not is_trusted_origin(request):
        raise PermissionDenied(
            'CSRF check failed: untrusted or missing origin.'
        )


def set_auth_cookie(response, name, token, lifetime):
    """Store a JWT in an HttpOnly cookie that expires with the token."""
    response.set_cookie(
        name,
        token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path='/',
    )


def set_token_cookies(response, access, refresh):
    set_auth_cookie(
        response, settings.AUTH_COOKIE_ACCESS, access,
        api_settings.ACCESS_TOKEN_LIFETIME,
    )
    set_auth_cookie(
        response, settings.AUTH_COOKIE_REFRESH, refresh,
        api_settings.REFRESH_TOKEN_LIFETIME,
    )
