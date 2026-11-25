
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_GET

from projects.models import Project
from tasks.models import TaskSubmission

from .forms import ReviewRequestForm
from .models import ProjectRequest


# ============================================================
# ROLE AND PERMISSION HELPERS
# ============================================================

def get_user_role(user):
    """
    Return the user's approved WorkSphere role.

    Django is_staff does not grant WorkSphere
    administrator permissions.
    """
    if not user.is_authenticated or not user.is_active:
        return None

    if user.is_superuser:
        return "admin"

    profile = getattr(user, "profile", None)

    if profile is None or not profile.is_approved:
        return None

    role = str(profile.role).strip().lower()

    if role in ("admin", "manager", "employee", "client"):
        return role

    return None


def client_required(view_func):
    """
    Only approved, active Clients may access
    Client Dashboard and Client project pages.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if get_user_role(request.user) != "client":
            raise PermissionDenied(
                "Only approved Clients can access this page."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def reviewer_required(view_func):
    """
    Only approved Admins and Managers may access
    the project-request review interface.

    Django staff status alone grants no access.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if get_user_role(request.user) not in (
            "admin",
            "manager",
        ):
            raise PermissionDenied(
                "Only approved Admins and Managers "
                "can review project requests."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================
# CLIENT PROJECT QUERYSET
# ============================================================

def get_client_projects(user):
    """
    Return only real projects assigned to this Client.

    Project.client is the authoritative relationship.
    """
    if get_user_role(user) != "client":
        return Project.objects.none()

    return (
        Project.objects.filter(client=user)
        .select_related("owner")
        .order_by("-created_at")
    )


def get_client_project(user, project_id):
    """
    Return an assigned Client project or HTTP 404.

    Clients cannot inspect projects belonging
    to other Clients by changing the URL.
    """
    return get_object_or_404(
        get_client_projects(user),
        pk=project_id,
    )


# ============================================================
# VERIFIED PROGRESS QUERYSET
# ============================================================

def get_project_tasks_with_review_status(project):
    """
    Return project tasks with the latest
    submission review status.

    Only the latest submission counts as the
    current review decision.
    """
    latest_submission = (
        TaskSubmission.objects.filter(
            task_id=OuterRef("pk")
        )
        .order_by("-submitted_at", "-pk")
        .values("status")[:1]
    )

    return (
        project.tasks.select_related("assigned_to")
        .annotate(
            latest_review_status=Subquery(
                latest_submission
            )
        )
        .order_by("created_at", "pk")
    )


# ============================================================
# CLIENT DASHBOARD
# ============================================================

@client_required
@require_GET
def client_dashboard(request):
    """
    Read-only dashboard showing projects assigned
    to the logged-in Client.

    dashboard_progress uses Manager-approved work,
    not employee-reported task completion.
    """
    project_list = list(
        get_client_projects(request.user)
    )

    for project in project_list:
        # Preserve these existing template variables.
        project.task_count = project.total_tasks
        project.done_count = project.approved_tasks

        # Verified progress displayed to Clients.
        project.dashboard_progress = (
            project.progress_percentage
        )

        # Additional statistics for future dashboard cards.
        project.employee_done_count = (
            project.completed_tasks
        )

        project.pending_review_count = (
            project.pending_review_tasks
        )

        project.rejected_count = (
            project.rejected_tasks
        )

        project.changes_requested_count = (
            project.changes_requested_tasks
        )

        project.remaining_count = (
            project.remaining_tasks
        )

        project.employee_progress = (
            project.employee_completion_percentage
        )

    context = {
        "projects": project_list,
        "total": len(project_list),
        "pending": sum(
            project.status == "planning"
            for project in project_list
        ),
        "active": sum(
            project.status == "in_progress"
            for project in project_list
        ),
        "completed": sum(
            project.status == "completed"
            for project in project_list
        ),
        "on_hold": sum(
            project.status == "on_hold"
            for project in project_list
        ),
    }

    return render(
        request,
        "clients/dashboard.html",
        context,
    )


# ============================================================
# CLIENT PROJECT DETAILS
# ============================================================

@client_required
@require_GET
def request_detail(request, pk):
    """
    Read-only details for a project assigned to
    the current Client.

    Clients cannot manage tasks, submit work,
    approve submissions or modify project data.
    """
    project = get_client_project(
        request.user,
        pk,
    )

    tasks = list(
        get_project_tasks_with_review_status(project)
    )

    # Verified project statistics.
    task_count = project.total_tasks
    approved_count = project.approved_tasks
    employee_completed_count = project.completed_tasks
    pending_review_count = project.pending_review_tasks
    rejected_count = project.rejected_tasks
    changes_requested_count = (
        project.changes_requested_tasks
    )

    context = {
        "project": project,
        "tasks": tasks,

        # Existing and additional context variables.
        "task_count": task_count,
        "total_tasks": task_count,

        "done_count": approved_count,
        "approved_tasks": approved_count,

        "employee_completed_tasks": (
            employee_completed_count
        ),

        "pending_review_tasks": pending_review_count,
        "rejected_tasks": rejected_count,
        "changes_requested_tasks": (
            changes_requested_count
        ),

        "remaining_tasks": project.remaining_tasks,

        "dashboard_progress": (
            project.progress_percentage
        ),

        "progress_percentage": (
            project.progress_percentage
        ),
    }

    return render(
        request,
        "clients/detail.html",
        context,
    )


# ============================================================
# CLIENT REQUEST CREATION
# ============================================================

@client_required
def create_request(request):
    """
    Clients have read-only access.

    Project request creation is intentionally disabled.
    """
    raise PermissionDenied(
        "Clients cannot create project requests."
    )


# ============================================================
# PROJECT REQUEST REVIEW LIST
# ============================================================

@reviewer_required
@require_GET
def review_requests(request):
    """
    Display project requests to authorized reviewers.

    ProjectRequest is separate from Project and does
    not grant Clients project management permissions.
    """
    project_requests = (
        ProjectRequest.objects
        .select_related("client")
        .order_by("-pk")
    )

    return render(
        request,
        "clients/review_list.html",
        {
            "requests": project_requests,
        },
    )


# ============================================================
# REVIEW PROJECT REQUEST
# ============================================================

@reviewer_required
def review_request(request, pk):
    """
    Allow authorized Admins and Managers to review
    an existing ProjectRequest.

    Preserve the existing ReviewRequestForm workflow.
    """
    project_request = get_object_or_404(
        ProjectRequest,
        pk=pk,
    )

    if request.method == "POST":
        form = ReviewRequestForm(
            request.POST,
            instance=project_request,
        )

        if form.is_valid():
            with transaction.atomic():
                form.save()

            messages.success(
                request,
                "Project request was updated successfully.",
            )

            return redirect("client_review_requests")

    else:
        form = ReviewRequestForm(
            instance=project_request
        )

    return render(
        request,
        "clients/form.html",
        {
            "form": form,
            "heading": "Review Project Request",
            "project_request": project_request,
        },
    )
