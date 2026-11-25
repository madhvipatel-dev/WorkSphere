
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpResponseForbidden
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from tasks.models import TaskSubmission

from .forms import ProjectForm, ProjectMemberForm
from .models import Project


# ============================================================
# ROLE AND PERMISSION HELPERS
# ============================================================

def get_user_role(user):
    """
    Return the active, approved WorkSphere role.

    Superusers are administrators.
    Django staff status alone grants no special access.
    """
    if not user.is_authenticated or not user.is_active:
        return None

    if user.is_superuser:
        return "admin"

    profile = getattr(user, "profile", None)

    if profile is None or not profile.is_approved:
        return None

    role = str(profile.role).strip().lower()

    if role not in (
        "admin",
        "manager",
        "employee",
        "client",
    ):
        return None

    return role


def project_creator_required(view_func):

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        if get_user_role(request.user) not in (
            "admin",
            "manager",
        ):
            return HttpResponseForbidden(
                "Only approved Admins and Managers "
                "can create projects."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def can_manage_project(user, project):
    """
    Superusers manage any project.

    Other approved Admins and Managers
    manage only projects they own.
    """
    if get_user_role(user) not in (
        "admin",
        "manager",
    ):
        return False

    return (
        user.is_superuser
        or project.owner_id == user.pk
    )


def accessible_projects(user):
    """
    Superuser: all projects.

    Admin/Manager/Employee: owned or joined projects.

    Client: explicitly assigned projects only.
    """
    role = get_user_role(user)

    if role is None:
        return Project.objects.none()

    if user.is_superuser:
        return Project.objects.all()

    if role == "client":
        return Project.objects.filter(client=user)

    return Project.objects.filter(
        Q(owner=user) | Q(members=user)
    ).distinct()


# ============================================================
# VERIFIED TASK STATISTICS
# ============================================================

def get_project_tasks(project):
    """
    Annotate each task with its latest
    submission review status.
    """
    latest_submission = (
        TaskSubmission.objects.filter(
            task_id=OuterRef("pk")
        )
        .order_by("-submitted_at", "-pk")
        .values("status")[:1]
    )

    return (
        project.tasks.select_related(
            "assigned_to",
            "created_by",
        )
        .annotate(
            latest_review_status=Subquery(
                latest_submission
            )
        )
        .order_by("created_at", "pk")
    )


def attach_project_progress(project):
    """
    Attach verified project progress
    information for templates.
    """
    project.task_count = project.total_tasks
    project.done_count = project.approved_tasks

    project.dashboard_progress = (
        project.progress_percentage
    )

    project.employee_done_count = (
        project.completed_tasks
    )

    project.employee_progress = (
        project.employee_completion_percentage
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

    return project


# ============================================================
# PROJECT LIST
# ============================================================

@login_required
def project_list(request):

    projects = list(
        accessible_projects(request.user)
        .select_related("owner", "client")
        .order_by("-created_at")
    )

    for project in projects:
        attach_project_progress(project)

    role = get_user_role(request.user)

    return render(
        request,
        "projects/project_list.html",
        {
            "projects": projects,
            "user_role": role,
            "can_create_project": role in (
                "admin",
                "manager",
            ),
        },
    )


# ============================================================
# CREATE PROJECT
# ============================================================

@project_creator_required
def project_create(request):

    if request.method == "POST":
        form = ProjectForm(request.POST)

        if form.is_valid():
            with transaction.atomic():

                project = form.save(commit=False)
                project.owner = request.user

                project.full_clean()
                project.save()

                form.save_m2m()

                project.members.add(request.user)

            messages.success(
                request,
                f'Project "{project.name}" '
                "was created successfully.",
            )

            return redirect("project_list")

    else:
        form = ProjectForm()

    return render(
        request,
        "projects/project_form.html",
        {
            "form": form,
            "page_title": "Create Project",
            "button_text": "Create Project",
        },
    )


# ============================================================
# PROJECT DETAIL
# ============================================================

@login_required
def project_detail(request, project_id):

    project = get_object_or_404(
        accessible_projects(request.user)
        .select_related("owner", "client")
        .prefetch_related("members"),
        pk=project_id,
    )

    role = get_user_role(request.user)

    can_manage = can_manage_project(
        request.user,
        project,
    )

    attach_project_progress(project)

    tasks = list(get_project_tasks(project))

    return render(
        request,
        "projects/project_detail.html",
        {
            "project": project,
            "tasks": tasks,
            "user_role": role,
            "can_manage_project": can_manage,
            "is_client": role == "client",

            "task_count": project.task_count,
            "done_count": project.done_count,
            "dashboard_progress": (
                project.dashboard_progress
            ),
            "approved_tasks": project.done_count,
            "pending_review_tasks": (
                project.pending_review_count
            ),
            "rejected_tasks": (
                project.rejected_count
            ),
            "changes_requested_tasks": (
                project.changes_requested_count
            ),
            "remaining_tasks": (
                project.remaining_count
            ),
            "employee_completed_tasks": (
                project.employee_done_count
            ),
            "employee_progress": (
                project.employee_progress
            ),
        },
    )


# ============================================================
# EDIT PROJECT
# ============================================================

@login_required
def project_edit(request, project_id):

    project = get_object_or_404(
        Project,
        pk=project_id,
    )

    if not can_manage_project(request.user, project):
        return HttpResponseForbidden(
            "You do not have permission "
            "to edit this project."
        )

    if request.method == "POST":
        form = ProjectForm(
            request.POST,
            instance=project,
        )

        if form.is_valid():
            with transaction.atomic():

                updated_project = form.save(
                    commit=False
                )

                # Project ownership cannot be changed here.
                updated_project.full_clean()
                updated_project.save()

                form.save_m2m()

                # Preserve owner membership.
                updated_project.members.add(
                    updated_project.owner
                )

            messages.success(
                request,
                f'Project "{updated_project.name}" '
                "was updated successfully.",
            )

            return redirect(
                "project_detail",
                project_id=updated_project.pk,
            )

    else:
        form = ProjectForm(instance=project)

    return render(
        request,
        "projects/project_form.html",
        {
            "form": form,
            "project": project,
            "page_title": "Edit Project",
            "button_text": "Save Changes",
        },
    )


# ============================================================
# DELETE PROJECT
# ============================================================

@login_required
def project_delete(request, project_id):

    project = get_object_or_404(
        Project,
        pk=project_id,
    )

    if not can_manage_project(request.user, project):
        return HttpResponseForbidden(
            "You do not have permission "
            "to delete this project."
        )

    if request.method == "POST":

        project_name = project.name

        project.delete()

        messages.success(
            request,
            f'Project "{project_name}" '
            "was deleted successfully.",
        )

        return redirect("project_list")

    return render(
        request,
        "projects/project_confirm_delete.html",
        {
            "project": project,
        },
    )


# ============================================================
# PROJECT TEAM MANAGEMENT
# ============================================================

@login_required
def project_members(request, project_id):

    project = get_object_or_404(
        Project,
        pk=project_id,
    )

    if not can_manage_project(request.user, project):
        return HttpResponseForbidden(
            "You do not have permission "
            "to manage this project's team."
        )

    if request.method == "POST":
        form = ProjectMemberForm(
            request.POST,
            instance=project,
        )

        if form.is_valid():
            with transaction.atomic():

                form.save()

                # The owner must remain a member.
                project.members.add(project.owner)

            messages.success(
                request,
                "Project team members "
                "were updated successfully.",
            )

            return redirect(
                "project_detail",
                project_id=project.pk,
            )

    else:
        form = ProjectMemberForm(
            instance=project
        )

    return render(
        request,
        "projects/project_members.html",
        {
            "form": form,
            "project": project,
        },
    )
