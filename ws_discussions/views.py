
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from projects.models import Project
from .models import Discussion


# ============================================================
# DISCUSSION ACCESS PERMISSION
# ============================================================

def internal_discussion_required(view_func):
    """
    Allow Discussions access only to approved, active
    Admin, Manager and Employee users.

    Client users cannot access any discussion endpoint.
    Superusers are treated as WorkSphere Admins.
    """

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        user = request.user

        if not user.is_active:
            return HttpResponseForbidden(
                "Your account is inactive."
            )

        # Superusers have Admin access.
        if user.is_superuser:
            return view_func(request, *args, **kwargs)

        profile = getattr(user, "profile", None)

        if profile is None:
            return HttpResponseForbidden(
                "Your account profile was not found."
            )

        if not profile.is_approved:
            return HttpResponseForbidden(
                "Your account is not approved."
            )

        if profile.role not in (
            "admin",
            "manager",
            "employee",
        ):
            return HttpResponseForbidden(
                "Clients are not allowed to access Discussions."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================
# PROJECT ACCESS PERMISSION
# ============================================================

def get_accessible_project(project_id, user):
    """
    Return a project only if the user is its owner
    or an assigned team member.

    Superusers can access all projects.
    """

    if user.is_superuser:
        queryset = Project.objects.all()
    else:
        queryset = Project.objects.filter(
            Q(owner=user) | Q(members=user)
        ).distinct()

    return get_object_or_404(
        queryset,
        id=project_id,
    )


# ============================================================
# FORMAT DISCUSSION MESSAGE
# ============================================================

def format_message(item, user):
    """
    Format discussion messages for AJAX responses.
    """

    return {
        "id": item.id,
        "author": (
            item.author.get_full_name()
            or item.author.get_username()
        ),
        "message": item.message,
        "created_at": item.created_at.strftime(
            "%d %b %Y, %I:%M %p"
        ),
        "is_mine": item.author_id == user.id,
    }


# ============================================================
# GENERAL TEAM DISCUSSIONS
# ============================================================

@internal_discussion_required
def discussion_list(request):
    """
    Display the latest 100 general team messages.
    Clients are not allowed.
    """

    messages = (
        Discussion.objects
        .filter(project__isnull=True)
        .select_related("author")
        .order_by("-created_at")[:100]
    )

    messages = list(reversed(messages))

    return render(
        request,
        "ws_discussions/discussion_list.html",
        {
            "messages": messages,
            "project": None,
        },
    )


# ============================================================
# SEND GENERAL DISCUSSION MESSAGE
# ============================================================

@internal_discussion_required
@require_POST
def send_message(request):
    """
    Allow internal users to send general messages.
    """

    message = request.POST.get(
        "message",
        "",
    ).strip()

    if message and len(message) <= 2000:

        Discussion.objects.create(
            author=request.user,
            message=message,
            project=None,
        )

    return redirect(
        "ws_discussions:discussion_list"
    )


# ============================================================
# GENERAL DISCUSSION MESSAGES JSON
# ============================================================

@internal_discussion_required
@require_GET
def messages_json(request):
    """
    Return general discussion messages for AJAX.
    Clients cannot retrieve this data.
    """

    messages = (
        Discussion.objects
        .filter(project__isnull=True)
        .select_related("author")
        .order_by("-created_at")[:100]
    )

    data = [
        format_message(item, request.user)
        for item in reversed(list(messages))
    ]

    return JsonResponse({
        "messages": data,
    })


# ============================================================
# PROJECT-WISE DISCUSSIONS
# ============================================================

@internal_discussion_required
def project_discussion_list(request, project_id):
    """
    Display project discussion messages.

    Only the project owner, project members,
    or a superuser can access the discussion.
    """

    project = get_accessible_project(
        project_id,
        request.user,
    )

    messages = (
        Discussion.objects
        .filter(project=project)
        .select_related("author")
        .order_by("-created_at")[:100]
    )

    messages = list(reversed(messages))

    return render(
        request,
        "ws_discussions/project_discussion.html",
        {
            "messages": messages,
            "project": project,
        },
    )


# ============================================================
# SEND PROJECT DISCUSSION MESSAGE
# ============================================================

@internal_discussion_required
@require_POST
def send_project_message(request, project_id):
    """
    Allow authorized project users to send messages.
    Clients cannot send project messages.
    """

    project = get_accessible_project(
        project_id,
        request.user,
    )

    message = request.POST.get(
        "message",
        "",
    ).strip()

    if message and len(message) <= 2000:

        Discussion.objects.create(
            project=project,
            author=request.user,
            message=message,
        )

    return redirect(
        "ws_discussions:project_discussion",
        project_id=project.id,
    )


# ============================================================
# PROJECT DISCUSSION MESSAGES JSON
# ============================================================

@internal_discussion_required
@require_GET
def project_messages_json(request, project_id):
    """
    Return project discussion messages for AJAX.

    Only authorized internal users can access
    the project messages.
    """

    project = get_accessible_project(
        project_id,
        request.user,
    )

    messages = (
        Discussion.objects
        .filter(project=project)
        .select_related("author")
        .order_by("-created_at")[:100]
    )

    data = [
        format_message(item, request.user)
        for item in reversed(list(messages))
    ]

    return JsonResponse({
        "messages": data,
    })
