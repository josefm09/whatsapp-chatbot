from django.urls import path
from . import views

urlpatterns = [
    path("webhook", views.meta_webhook),
    path("verify", views.meta_verify),
]
