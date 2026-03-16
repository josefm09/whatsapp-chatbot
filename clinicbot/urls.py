from django.contrib import admin
from django.urls import path, include
from whatsappbot.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("meta/", include("whatsappbot.urls")),
    path("health", health),
]
