from django.conf import settings
from rest_framework.permissions import SAFE_METHODS
from rest_framework_simplejwt.authentication import JWTAuthentication

from .utils import enforce_trusted_origin


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate with the JWT from the HttpOnly access cookie.

    The Authorization header is ignored on purpose: the frontend never sees
    the token. Because browsers attach cookies automatically, state-changing
    requests must additionally come from a trusted origin (CSRF protection,
    like DRF's SessionAuthentication.enforce_csrf).
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw_token:
            return None
        validated_token = self.get_validated_token(raw_token)
        user = self.get_user(validated_token)
        if request.method not in SAFE_METHODS:
            enforce_trusted_origin(request)
        return user, validated_token
