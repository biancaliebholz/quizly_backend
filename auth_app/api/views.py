from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .serializers import (
    INVALID_CREDENTIALS_MESSAGE,
    LoginSerializer,
    RegistrationSerializer,
    UserSummarySerializer,
)
from .utils import (
    blacklist_refresh_cookie,
    block_access_token,
    delete_token_cookies,
    enforce_trusted_origin,
    has_origin_headers,
    is_trusted_origin,
    set_access_cookie,
    set_token_cookies,
)

User = get_user_model()

TOKEN_REFRESHED_MESSAGE = 'Token refreshed'
LOGOUT_MESSAGE = (
    'Log-Out successfully! All Tokens will be deleted. '
    'Refresh token is now invalid.'
)


class RegistrationView(generics.CreateAPIView):
    """Public endpoint that registers a new user account."""

    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        """Create the user and return the documented confirmation message."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {'detail': 'User created successfully!'},
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """Log a user in and deliver the JWT pair only as HttpOnly cookies.

    No authentication classes: a stale access cookie must not block login.
    Origin/Referer are checked when present (login CSRF); requests without
    both headers (e.g. Postman) are allowed.
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """Log in: 403 for an untrusted origin, 401 for any invalid input."""
        if has_origin_headers(request):
            enforce_trusted_origin(request)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            raise AuthenticationFailed(INVALID_CREDENTIALS_MESSAGE)
        return self.build_login_response(serializer)

    def build_login_response(self, serializer):
        """Return the documented body; the tokens go into cookies only."""
        user_data = UserSummarySerializer(serializer.user).data
        body = {'detail': 'Login successfully!', 'user': user_data}
        response = Response(body)
        tokens = serializer.validated_data
        set_token_cookies(response, tokens['access'], tokens['refresh'])
        return response


class TokenRefreshCookieView(TokenRefreshView):
    """Issue a new access cookie from the refresh cookie (no rotation).

    The refresh cookie authenticates this request, so the Origin/Referer
    check is strict. A stale access cookie must not block the refresh.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        """403 for an untrusted origin, 401 for a missing or invalid cookie."""
        enforce_trusted_origin(request)
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw_token:
            raise NotAuthenticated('Refresh token cookie is missing.')
        access = self.get_new_access_token(raw_token)
        response = Response({'detail': TOKEN_REFRESHED_MESSAGE})
        set_access_cookie(response, access)
        return response

    def get_new_access_token(self, raw_token):
        """Validate the refresh token (incl. blacklist) and issue an access."""
        serializer = self.get_serializer(data={'refresh': raw_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as error:
            raise InvalidToken(error.args[0]) from error
        except User.DoesNotExist as error:
            raise InvalidToken('User not found.') from error
        return serializer.validated_data['access']


class LogoutView(APIView):
    """Revoke both JWTs immediately and delete their cookies.

    Uses the default cookie authentication including the Origin check.
    Without a valid access token the response stays 401 as documented, but
    a request from the trusted frontend still revokes the refresh token and
    deletes the cookies, so the user is really logged out.
    """

    def post(self, request):
        """Revoke both tokens (blacklist + jti block) and clear the cookies."""
        blacklist_refresh_cookie(request)
        block_access_token(request.auth)
        response = Response({'detail': LOGOUT_MESSAGE})
        delete_token_cookies(response)
        return response

    def handle_exception(self, exc):
        """Keep 401, but still log out a trusted frontend with an old token."""
        response = super().handle_exception(exc)
        unauthorized = response.status_code == status.HTTP_401_UNAUTHORIZED
        if unauthorized and is_trusted_origin(self.request):
            blacklist_refresh_cookie(self.request)
            delete_token_cookies(response)
        return response
