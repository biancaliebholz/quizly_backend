from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    RegistrationView,
    TokenRefreshCookieView,
)

urlpatterns = [
    path('register/', RegistrationView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path(
        'token/refresh/',
        TokenRefreshCookieView.as_view(),
        name='token_refresh',
    ),
    path('logout/', LogoutView.as_view(), name='logout'),
]
