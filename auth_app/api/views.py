from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    INVALID_CREDENTIALS_MESSAGE,
    LoginSerializer,
    RegistrationSerializer,
    UserSummarySerializer,
)
from .utils import (
    enforce_trusted_origin,
    has_origin_headers,
    set_token_cookies,
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
        if has_origin_headers(request):
            enforce_trusted_origin(request)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            raise AuthenticationFailed(INVALID_CREDENTIALS_MESSAGE)
        return self.build_login_response(serializer)

    def build_login_response(self, serializer):
        user_data = UserSummarySerializer(serializer.user).data
        body = {'detail': 'Login successfully!', 'user': user_data}
        response = Response(body)
        tokens = serializer.validated_data
        set_token_cookies(response, tokens['access'], tokens['refresh'])
        return response
