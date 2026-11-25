
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def home_redirect(request):
    return redirect("login")


urlpatterns = [

    # Django Administration
    path(
        "admin/",
        admin.site.urls,
    ),

    # Authentication
    path(
        "accounts/",
        include("accounts.urls"),
    ),

    # Dashboard
    path(
        "dashboard/",
        include("dashboard.urls"),
    ),

    # Project Management
    path(
        "projects/",
        include("projects.urls"),
    ),

    # Task Management
    path(
        "tasks/",
        include("tasks.urls"),
    ),

    # Meeting Management
    path(
        "meetings/",
        include("meetings.urls"),
    ),

    # File Management
    path(
        "files/",
        include("files.urls"),
    ),

    # Notifications
    path(
        "notifications/",
        include("notifications.urls"),
    ),

    # Department Management
    path(
        "departments/",
        include("ws_departments.urls"),
    ),

    # Team Management
    path(
        "team/",
        include("worksphere_team.urls"),
    ),

    # Project Discussions
    path(
        "discussions/",
        include("ws_discussions.urls"),
    ),

    # Audit Logs
    path(
        "audit-logs/",
        include("ws_audit.urls"),
    ),

    # Client Dashboard
    path(
        "client/",
        include("clients.urls"),
    ),

    path(
        "dashboard/client/",
        include("clients.urls"),
    ),

    # Home
    path(
        "",
        home_redirect,
        name="home",
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
