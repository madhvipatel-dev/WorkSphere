
from django.urls import path
from . import views

urlpatterns = [
    path(
        "",
        views.client_dashboard,
        name="client_dashboard",
    ),
    path(
        "request/new/",
        views.create_request,
        name="client_create_request",
    ),
    path(
        "request/<int:pk>/",
        views.request_detail,
        name="client_request_detail",
    ),
    path(
        "review/",
        views.review_requests,
        name="client_review_requests",
    ),
    path(
        "review/<int:pk>/",
        views.review_request,
        name="client_review_request",
    ),
]
