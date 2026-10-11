"""Root URLs: Django admin and the JSON API (auth and quizzes) under /api/."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('auth_app.api.urls')),
    path('api/', include('quizzes_app.api.urls')),
]
