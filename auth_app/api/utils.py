from urllib.parse import urlsplit

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import datetime_from_epoch

from ..models import BlockedAccessToken


def get_url_origin(url):
    """Return the 'scheme://host[:port]' part of a URL."""
    parts = urlsplit(url)
    return f'{parts.scheme}://{parts.netloc}'


def has_origin_headers(request):
    """True if the request carries an Origin or Referer header."""
    return 'HTTP_ORIGIN' in request.META or 'HTTP_REFERER' in request.META


def get_request_origin(request):
    """Return the Origin header, falling back to the Referer's origin."""
    origin = request.META.get('HTTP_ORIGIN')
    if origin is not None:
        return origin
    referer = request.META.get('HTTP_REFERER')
    return get_url_origin(referer) if referer else None


def is_trusted_origin(request):
    """True if Origin (or the Referer origin) is a trusted frontend."""
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


def set_access_cookie(response, access):
    set_auth_cookie(
        response, settings.AUTH_COOKIE_ACCESS, access,
        api_settings.ACCESS_TOKEN_LIFETIME,
    )


def set_token_cookies(response, access, refresh):
    """Set the access and refresh JWT as HttpOnly cookies."""
    set_access_cookie(response, access)
    set_auth_cookie(
        response, settings.AUTH_COOKIE_REFRESH, refresh,
        api_settings.REFRESH_TOKEN_LIFETIME,
    )


def delete_token_cookies(response):
    """Expire both JWT cookies (same path and SameSite as when set)."""
    for name in (settings.AUTH_COOKIE_ACCESS, settings.AUTH_COOKIE_REFRESH):
        response.delete_cookie(
            name, path='/', samesite=settings.AUTH_COOKIE_SAMESITE
        )


def blacklist_refresh_cookie(request):
    """Blacklist the refresh token from the cookie if it is still usable.

    A missing, invalid, expired or already blacklisted token cannot be used
    anymore, so there is nothing left to revoke.
    """
    raw_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
    if not raw_token:
        return
    try:
        RefreshToken(raw_token).blacklist()
    except TokenError:
        return


def block_access_token(token):
    """Block an access token by its jti until it would expire anyway."""
    BlockedAccessToken.objects.get_or_create(
        jti=token[api_settings.JTI_CLAIM],
        defaults={'expires_at': datetime_from_epoch(token['exp'])},
    )


def is_access_token_blocked(token):
    """True if a logout revoked this access token (blocked jti)."""
    jti = token[api_settings.JTI_CLAIM]
    return BlockedAccessToken.objects.filter(jti=jti).exists()
