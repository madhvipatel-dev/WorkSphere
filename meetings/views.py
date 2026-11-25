
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
)

from projects.models import Project

from .forms import (
    MeetingForm,
    can_manage_meetings,
    get_manageable_projects,
    get_project_participants,
    get_user_role,
)
from .models import Meeting


User = get_user_model()


# ============================================================
# MEETING ACCESS DECORATOR
# ============================================================

def meeting_access_required(view_func):
    """
    Allow active, approved internal users.

    Admin, Manager, Employee:
        Allowed to access Meetings according to
        their existing permissions.

    Client:
        Show an Access Denied page with a button
        to return to the Client Dashboard.

    Superuser:
        Treated as WorkSphere Admin.

    Django is_staff alone does not grant access.
    """

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        role = get_user_role(request.user)

        # Clients cannot access Meetings.
        if role == "client":
            return render(
                request,
                "accounts/client_access_denied.html",
                {
                    "module_name": "Meetings",
                },
                status=403,
            )

        # Block inactive, unapproved or unauthorized users.
        if role not in (
            "admin",
            "manager",
            "employee",
        ):
            raise PermissionDenied(
                "You do not have permission "
                "to access Meeting Management."
            )

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper


# ============================================================
# ACCESSIBLE PROJECTS
# ============================================================

def accessible_meeting_projects(user):
    """
    Return projects whose meetings the user
    is allowed to view.

    Superuser:
        All projects.

    Admin / Manager:
        Projects they own or belong to.

    Employee:
        Projects where they are a member.

    Client:
        No internal meeting access.
    """

    role = get_user_role(user)

    if role not in (
        "admin",
        "manager",
        "employee",
    ):
        return Project.objects.none()

    if user.is_superuser:
        return Project.objects.all()

    if role in (
        "admin",
        "manager",
    ):
        return Project.objects.filter(
            Q(owner=user) | Q(members=user)
        ).distinct()

    return Project.objects.filter(
        members=user,
    ).distinct()


# ============================================================
# ACCESSIBLE MEETINGS
# ============================================================

def accessible_meetings(user):
    """
    Return meetings belonging to projects
    the user can currently access.

    Past organizer or participant membership
    does not bypass current project access.
    """

    projects = accessible_meeting_projects(user)

    return (
        Meeting.objects
        .filter(project__in=projects)
        .select_related(
            "project",
            "organizer",
        )
        .prefetch_related(
            "participants",
        )
        .distinct()
    )


# ============================================================
# MEETING MANAGEMENT PERMISSIONS
# ============================================================

def can_manage_project_meetings(user, project):
    """
    Superuser:
        Can manage meetings in any project.

    Admin / Manager:
        Can manage meetings in projects they own.

    Employee / Client:
        Cannot manage meetings.
    """

    if not can_manage_meetings(user):
        return False

    if user.is_superuser:
        return True

    return project.owner_id == user.pk


def can_edit_meeting(user, meeting):
    """
    Authorized project managers can edit
    meetings within their own projects.
    """

    return can_manage_project_meetings(
        user,
        meeting.project,
    )


def can_delete_meeting(user, meeting):
    """
    Authorized project managers can delete
    meetings within their own projects.
    """

    return can_manage_project_meetings(
        user,
        meeting.project,
    )


def get_accessible_meeting_or_404(user, meeting_id):
    """
    Return a meeting only when the user has
    current project-level access.
    """

    return get_object_or_404(
        accessible_meetings(user),
        pk=meeting_id,
    )


# ============================================================
# COMMON TEMPLATE CONTEXT
# ============================================================

def meeting_permission_context(user, meeting=None):

    context = {
        "user_role": get_user_role(user),
        "can_create_meeting": (
            get_manageable_projects(user).exists()
        ),
        "can_edit_meeting": False,
        "can_delete_meeting": False,
    }

    if meeting is not None:
        context["can_edit_meeting"] = (
            can_edit_meeting(user, meeting)
        )

        context["can_delete_meeting"] = (
            can_delete_meeting(user, meeting)
        )

    return context


# ============================================================
# MEETING LIST
# ============================================================

@meeting_access_required
@require_GET
def meeting_list(request):

    meetings = accessible_meetings(
        request.user
    )

    total_meetings = meetings.count()

    scheduled_meetings = meetings.filter(
        status="scheduled"
    ).count()

    completed_meetings = meetings.filter(
        status="completed"
    ).count()

    cancelled_meetings = meetings.filter(
        status="cancelled"
    ).count()

    context = {
        "meetings": meetings,
        "total_meetings": total_meetings,
        "scheduled_meetings": scheduled_meetings,
        "completed_meetings": completed_meetings,
        "cancelled_meetings": cancelled_meetings,
    }

    context.update(
        meeting_permission_context(
            request.user
        )
    )

    return render(
        request,
        "meetings/meeting_list.html",
        context,
    )


# ============================================================
# CREATE MEETING
# ============================================================

@meeting_access_required
@require_http_methods(["GET", "POST"])
def meeting_create(request):

    if not can_manage_meetings(
        request.user
    ):
        raise PermissionDenied(
            "Only approved Admins and Managers "
            "can create meetings."
        )

    if not get_manageable_projects(
        request.user
    ).exists():

        messages.warning(
            request,
            "You must own an eligible project "
            "before creating a meeting."
        )

        return redirect(
            "meeting_list"
        )

    if request.method == "POST":

        form = MeetingForm(
            request.user,
            request.POST,
        )

        if form.is_valid():

            meeting = form.save()

            messages.success(
                request,
                f'Meeting "{meeting.title}" '
                f"was created successfully."
            )

            return redirect(
                "meeting_detail",
                meeting_id=meeting.pk,
            )

    else:

        initial = {}

        project_id = request.GET.get(
            "project"
        )

        if project_id:

            selected_project = (
                get_manageable_projects(
                    request.user
                ).filter(
                    pk=project_id
                ).first()
            )

            if selected_project:

                initial["project"] = (
                    selected_project.pk
                )

        form = MeetingForm(
            request.user,
            initial=initial,
        )

    context = {
        "form": form,
        "page_title": "Create Meeting",
        "button_text": "Create Meeting",
        "is_editing": False,
    }

    context.update(
        meeting_permission_context(
            request.user
        )
    )

    return render(
        request,
        "meetings/meeting_form.html",
        context,
    )


# ============================================================
# MEETING DETAILS
# ============================================================

@meeting_access_required
@require_GET
def meeting_detail(request, meeting_id):

    meeting = get_accessible_meeting_or_404(
        request.user,
        meeting_id,
    )

    context = {
        "meeting": meeting,
    }

    context.update(
        meeting_permission_context(
            request.user,
            meeting,
        )
    )

    return render(
        request,
        "meetings/meeting_detail.html",
        context,
    )


# ============================================================
# EDIT MEETING
# ============================================================

@meeting_access_required
@require_http_methods(["GET", "POST"])
def meeting_edit(request, meeting_id):

    meeting = get_accessible_meeting_or_404(
        request.user,
        meeting_id,
    )

    if not can_edit_meeting(
        request.user,
        meeting,
    ):
        raise PermissionDenied(
            "You do not have permission "
            "to edit this meeting."
        )

    if request.method == "POST":

        form = MeetingForm(
            request.user,
            request.POST,
            instance=meeting,
        )

        if form.is_valid():

            updated_meeting = form.save()

            messages.success(
                request,
                f'Meeting "{updated_meeting.title}" '
                f"was updated successfully."
            )

            return redirect(
                "meeting_detail",
                meeting_id=updated_meeting.pk,
            )

    else:

        form = MeetingForm(
            request.user,
            instance=meeting,
        )

    context = {
        "form": form,
        "meeting": meeting,
        "page_title": "Edit Meeting",
        "button_text": "Save Changes",
        "is_editing": True,
    }

    context.update(
        meeting_permission_context(
            request.user,
            meeting,
        )
    )

    return render(
        request,
        "meetings/meeting_form.html",
        context,
    )


# ============================================================
# DELETE MEETING
# ============================================================

@meeting_access_required
@require_http_methods(["GET", "POST"])
def meeting_delete(request, meeting_id):

    meeting = get_accessible_meeting_or_404(
        request.user,
        meeting_id,
    )

    if not can_delete_meeting(
        request.user,
        meeting,
    ):
        raise PermissionDenied(
            "You do not have permission "
            "to delete this meeting."
        )

    if request.method == "POST":

        meeting_title = meeting.title

        meeting.delete()

        messages.success(
            request,
            f'Meeting "{meeting_title}" '
            f"was deleted successfully."
        )

        return redirect(
            "meeting_list"
        )

    context = {
        "meeting": meeting,
    }

    context.update(
        meeting_permission_context(
            request.user,
            meeting,
        )
    )

    return render(
        request,
        "meetings/meeting_confirm_delete.html",
        context,
    )


# ============================================================
# PROJECT PARTICIPANTS API
# ============================================================

@meeting_access_required
@require_GET
def meeting_project_participants(request):
    """
    Return eligible meeting participants
    for a selected project.

    Only authorized Admins and Managers can
    retrieve project participant information.
    """

    if not can_manage_meetings(
        request.user
    ):
        raise PermissionDenied(
            "You cannot manage meeting participants."
        )

    project_id = request.GET.get(
        "project_id"
    )

    if not project_id:
        return JsonResponse(
            {"participants": []}
        )

    project = get_object_or_404(
        get_manageable_projects(
            request.user
        ),
        pk=project_id,
    )

    participants = get_project_participants(
        project
    )

    data = [
        {
            "id": participant.pk,
            "username": participant.username,
            "display_name": (
                participant.get_full_name()
                or participant.username
            ),
        }
        for participant in participants
    ]

    return JsonResponse(
        {
            "project_id": project.pk,
            "participants": data,
        }
    )
