
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from projects.models import Project
from notifications.models import Notification

from .forms import TaskForm, TaskSubmissionForm
from .models import Task, TaskSubmission, TaskComment


# ============================================================
# ROLE AND PERMISSION HELPERS
# ============================================================

def get_user_role(user):
    """
    Return the user's approved WorkSphere role.

    Django staff status alone does not grant WorkSphere
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

    if role not in ("admin", "manager", "employee", "client"):
        return None

    return role


def is_admin(user):
    return get_user_role(user) == "admin"


def is_manager(user):
    return get_user_role(user) == "manager"


def is_employee(user):
    return get_user_role(user) == "employee"


def can_manage_project(user, project):
    """
    Superusers may manage any project.

    Approved Admins and Managers can manage tasks in
    projects they own or have joined as team members.

    This helper controls TASK management only; it does
    not change project edit/delete permissions.
    """
    role = get_user_role(user)

    if role not in ("admin", "manager"):
        return False

    return (
        user.is_superuser
        or project.owner_id == user.pk
        or project.members.filter(pk=user.pk).exists()
    )


def can_access_task(user, task):
    """
    Internal users may access tasks belonging to
    their owned or joined projects.

    Clients cannot access internal task pages.
    """
    role = get_user_role(user)

    if role not in ("admin", "manager", "employee"):
        return False

    if user.is_superuser:
        return True

    return (
        task.project.owner_id == user.pk
        or task.project.members.filter(pk=user.pk).exists()
    )


def can_manage_task(user, task):
    return can_manage_project(user, task.project)


def can_work_on_task(user, task):
    """
    Only the assigned, approved Employee may update
    task status or submit work.
    """
    return (
        is_employee(user)
        and task.assigned_to_id == user.pk
        and (
            task.project.owner_id == user.pk
            or task.project.members.filter(pk=user.pk).exists()
        )
    )


def internal_user_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if get_user_role(request.user) not in (
            "admin",
            "manager",
            "employee",
        ):
            return HttpResponseForbidden(
                "You do not have permission "
                "to access internal task management."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def manager_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if get_user_role(request.user) not in (
            "admin",
            "manager",
        ):
            return HttpResponseForbidden(
                "Only approved Admins and Managers "
                "can manage tasks."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def employee_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_employee(request.user):
            return HttpResponseForbidden(
                "Only approved Employees "
                "can perform this action."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================
# ACCESSIBLE PROJECTS AND TASKS
# ============================================================

def accessible_projects(user):
    role = get_user_role(user)

    if role not in ("admin", "manager", "employee"):
        return Project.objects.none()

    if user.is_superuser:
        return Project.objects.all()

    return Project.objects.filter(
        Q(owner=user) | Q(members=user)
    ).distinct()


def accessible_tasks(user):
    return Task.objects.filter(
        project__in=accessible_projects(user)
    ).distinct()


# ============================================================
# NOTIFICATIONS
# ============================================================

def notify_user(
    recipient,
    title,
    message,
    notification_type,
    task,
):
    """
    Create a notification using the existing
    WorkSphere Notification model.
    """
    if recipient is None or not recipient.is_active:
        return

    Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        related_task=task,
    )


# ============================================================
# SUBMISSION HELPERS
# ============================================================

def get_latest_submission(task):
    """
    Return the most recent submission for a task.

    Submission status and task status are separate:
    a completed task may still be awaiting review.
    """
    return (
        TaskSubmission.objects.filter(task=task)
        .order_by("-submitted_at", "-pk")
        .first()
    )


def get_submission_state(task):
    """
    Return the state of the most recent submission.

    none:
        No submission exists.

    pending:
        A submission is waiting for review.

    approved:
        The latest submission was approved.

    rejected / changes_requested:
        The employee may submit revised work.
    """
    latest_submission = get_latest_submission(task)

    if latest_submission is None:
        return "none", None

    return latest_submission.status, latest_submission


# ============================================================
# TASK LIST
# ============================================================

@internal_user_required
def task_list(request):
    user = request.user

    tasks = accessible_tasks(user).select_related(
        "project",
        "assigned_to",
        "created_by",
    )

    search_query = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "").strip()
    priority_filter = request.GET.get("priority", "").strip()
    project_filter = request.GET.get("project", "").strip()

    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(project__name__icontains=search_query)
        )

    valid_statuses = {
        choice[0] for choice in Task.STATUS_CHOICES
    }

    valid_priorities = {
        choice[0] for choice in Task.PRIORITY_CHOICES
    }

    if status_filter in valid_statuses:
        tasks = tasks.filter(status=status_filter)

    if priority_filter in valid_priorities:
        tasks = tasks.filter(priority=priority_filter)

    if project_filter.isdigit():
        tasks = tasks.filter(
            project_id=int(project_filter)
        )

    context = {
        "tasks": tasks,
        "projects": accessible_projects(user),
        "search_query": search_query,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "project_filter": project_filter,
        "status_choices": Task.STATUS_CHOICES,
        "priority_choices": Task.PRIORITY_CHOICES,
        "user_role": get_user_role(user),
        "can_create_task": get_user_role(user)
        in ("admin", "manager"),
    }

    return render(
        request,
        "tasks/task_list.html",
        context,
    )


# ============================================================
# EMPLOYEE TASK LIST
# ============================================================

@employee_required
def employee_task_list(request):
    user = request.user

    tasks = accessible_tasks(user).filter(
        assigned_to=user
    ).select_related(
        "project",
        "created_by",
        "assigned_to",
    )

    search_query = request.GET.get("search", "").strip()
    project_filter = request.GET.get("project", "").strip()
    status_filter = request.GET.get("status", "").strip()
    priority_filter = request.GET.get("priority", "").strip()

    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(project__name__icontains=search_query)
        )

    if project_filter.isdigit():
        tasks = tasks.filter(
            project_id=int(project_filter)
        )

    valid_statuses = {
        choice[0] for choice in Task.STATUS_CHOICES
    }

    valid_priorities = {
        choice[0] for choice in Task.PRIORITY_CHOICES
    }

    if status_filter in valid_statuses:
        tasks = tasks.filter(status=status_filter)

    if priority_filter in valid_priorities:
        tasks = tasks.filter(priority=priority_filter)

    context = {
        "tasks": tasks,
        "projects": accessible_projects(user).filter(
            tasks__assigned_to=user
        ).distinct(),
        "search_query": search_query,
        "project_filter": project_filter,
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "status_choices": Task.STATUS_CHOICES,
        "priority_choices": Task.PRIORITY_CHOICES,
        "total_tasks": tasks.count(),
        "todo_tasks": tasks.filter(
            status="todo"
        ).count(),
        "in_progress_tasks": tasks.filter(
            status="in_progress"
        ).count(),
        "completed_tasks": tasks.filter(
            status="completed"
        ).count(),
        "blocked_tasks": tasks.filter(
            status="blocked"
        ).count(),
        "today": timezone.localdate(),
    }

    return render(
        request,
        "tasks/my_tasks.html",
        context,
    )


# ============================================================
# UPDATE TASK STATUS
# ============================================================

@employee_required
@require_POST
def update_task_status(request, task_id):
    new_status = request.POST.get("status", "").strip()

    valid_statuses = {
        choice[0] for choice in Task.STATUS_CHOICES
    }

    if new_status not in valid_statuses:
        messages.error(
            request,
            "Invalid task status selected.",
        )
        return redirect("employee_task_list")

    with transaction.atomic():
        task = get_object_or_404(
            Task.objects.select_for_update().select_related(
                "project",
            ),
            pk=task_id,
            assigned_to=request.user,
        )

        if not can_work_on_task(request.user, task):
            return HttpResponseForbidden(
                "You cannot update this task."
            )

        submission_state, latest_submission = (
            get_submission_state(task)
        )

        if submission_state == "pending":
            messages.warning(
                request,
                "This task has work awaiting review. "
                "Its status cannot be changed until "
                "the Manager reviews the submission.",
            )
            return redirect("employee_task_list")

        if submission_state == "approved":
            messages.warning(
                request,
                "This task's submitted work has already "
                "been approved. Its status is locked.",
            )
            return redirect("employee_task_list")

        if task.status == new_status:
            messages.info(
                request,
                "The task already has this status.",
            )
            return redirect("employee_task_list")

        old_status = task.get_status_display()

        task.status = new_status
        task.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        task_title = task.title
        status_display = task.get_status_display()

    messages.success(
        request,
        f'Task "{task_title}" status changed '
        f"from {old_status} to {status_display}.",
    )

    return redirect("employee_task_list")


# ============================================================
# SUBMIT COMPLETED WORK
# ============================================================

@employee_required
def submit_work(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related(
            "project",
            "project__owner",
            "assigned_to",
            "created_by",
        ),
        pk=task_id,
        assigned_to=request.user,
    )

    if not can_work_on_task(request.user, task):
        return HttpResponseForbidden(
            "You cannot submit work for this task."
        )

    previous_submissions = (
        TaskSubmission.objects.filter(
            task=task,
            submitted_by=request.user,
        )
        .select_related("submitted_by")
        .order_by("-submitted_at", "-pk")
    )

    submission_state, latest_submission = (
        get_submission_state(task)
    )

    if submission_state == "approved":
        messages.info(
            request,
            "The submitted work for this task "
            "has already been approved.",
        )
        return redirect("employee_task_list")

    if task.status != "completed":
        messages.warning(
            request,
            "Please mark the task as Completed "
            "before submitting your work.",
        )
        return redirect("employee_task_list")

    if request.method == "POST":
        form = TaskSubmissionForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            with transaction.atomic():
                # Lock the parent task to serialize submission
                # creation for this task.
                locked_task = get_object_or_404(
                    Task.objects.select_for_update(),
                    pk=task.pk,
                    assigned_to=request.user,
                )

                if not can_work_on_task(
                    request.user,
                    locked_task,
                ):
                    return HttpResponseForbidden(
                        "You cannot submit work for this task."
                    )

                current_state, current_submission = (
                    get_submission_state(locked_task)
                )

                if current_state == "pending":
                    messages.warning(
                        request,
                        "Your previous submission is still "
                        "waiting for review.",
                    )
                    return redirect("employee_task_list")

                if current_state == "approved":
                    messages.warning(
                        request,
                        "Work for this task has already "
                        "been approved.",
                    )
                    return redirect("employee_task_list")

                if locked_task.status != "completed":
                    messages.warning(
                        request,
                        "Please mark the task as Completed "
                        "before submitting work.",
                    )
                    return redirect("employee_task_list")

                submission = form.save(commit=False)
                submission.task = locked_task
                submission.submitted_by = request.user
                submission.status = "pending"
                submission.save()

                employee_name = (
                    request.user.get_full_name()
                    or request.user.username
                )

                recipients = []

                if (
                    task.created_by_id
                    and task.created_by_id != request.user.pk
                ):
                    recipients.append(task.created_by)

                if (
                    task.project.owner_id
                    and task.project.owner_id != request.user.pk
                    and task.project.owner not in recipients
                ):
                    recipients.append(task.project.owner)

                for recipient in recipients:
                    notify_user(
                        recipient=recipient,
                        title="Work Submitted for Review",
                        message=(
                            f"{employee_name} submitted work "
                            f'for the task "{task.title}". '
                            "Please review the submission."
                        ),
                        notification_type="work_submitted",
                        task=task,
                    )

            messages.success(
                request,
                f'Work for "{task.title}" was submitted '
                "successfully and is awaiting review.",
            )

            return redirect("employee_task_list")

    else:
        form = TaskSubmissionForm()

    return render(
        request,
        "tasks/submit_work.html",
        {
            "task": task,
            "form": form,
            "previous_submissions": previous_submissions,
            "has_pending_submission": (
                submission_state == "pending"
            ),
            "latest_submission": latest_submission,
            "submission_state": submission_state,
            "can_submit_work": (
                submission_state not in ("pending", "approved")
            ),
        },
    )


# ============================================================
# CREATE TASK
# ============================================================

@manager_required
def task_create(request):
    user = request.user

    if request.method == "POST":
        form = TaskForm(
            request.POST,
            user=user,
        )

        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = user

            if not can_manage_project(
                user,
                task.project,
            ):
                return HttpResponseForbidden(
                    "You cannot create tasks "
                    "in this project."
                )

            if (
                task.assigned_to_id
                and not task.project.members.filter(
                    pk=task.assigned_to_id
                ).exists()
            ):
                form.add_error(
                    "assigned_to",
                    "The assigned employee must be "
                    "a member of the selected project.",
                )

            else:
                with transaction.atomic():
                    task.save()
                    form.save_m2m()

                    if (
                        task.assigned_to
                        and task.assigned_to != user
                    ):
                        creator_name = (
                            user.get_full_name()
                            or user.username
                        )

                        notify_user(
                            recipient=task.assigned_to,
                            title="New Task Assigned",
                            message=(
                                "You have been assigned "
                                f'the task "{task.title}" '
                                f"by {creator_name}."
                            ),
                            notification_type="task_assigned",
                            task=task,
                        )

                messages.success(
                    request,
                    f'Task "{task.title}" '
                    "was created successfully.",
                )

                return redirect("task_list")

    else:
        form = TaskForm(user=user)

    return render(
        request,
        "tasks/task_form.html",
        {
            "form": form,
            "page_title": "Create Task",
            "button_text": "Create Task",
        },
    )


# ============================================================
# TASK DETAILS
# ============================================================

@internal_user_required
def task_detail(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related(
            "project",
            "assigned_to",
            "created_by",
        ),
        pk=task_id,
    )

    if not can_access_task(request.user, task):
        return HttpResponseForbidden(
            "You do not have permission "
            "to view this task."
        )

    submissions = (
        task.submissions
        .select_related("submitted_by")
        .order_by("-submitted_at", "-pk")
    )

    comments = (
        task.comments
        .select_related("user")
        .all()
    )

    submission_state, latest_submission = (
        get_submission_state(task)
    )

    return render(
        request,
        "tasks/task_detail.html",
        {
            "task": task,
            "submissions": submissions,
            "comments": comments,
            "can_manage_task": can_manage_task(
                request.user,
                task,
            ),
            "can_work_on_task": can_work_on_task(
                request.user,
                task,
            ),
            "user_role": get_user_role(request.user),
            "latest_submission": latest_submission,
            "submission_state": submission_state,
            "has_pending_submission": (
                submission_state == "pending"
            ),
            "has_approved_submission": (
                submission_state == "approved"
            ),
        },
    )


# ============================================================
# ADD TASK COMMENT
# ============================================================

@internal_user_required
@require_POST
def add_task_comment(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related(
            "project",
            "assigned_to",
            "created_by",
        ),
        pk=task_id,
    )

    if not can_access_task(request.user, task):
        return HttpResponseForbidden(
            "You do not have permission "
            "to comment on this task."
        )

    comment_text = request.POST.get(
        "comment", ""
    ).strip()

    if not comment_text:
        messages.error(
            request,
            "Comment cannot be empty.",
        )
        return redirect(
            "task_detail",
            task_id=task.pk,
        )

    TaskComment.objects.create(
        task=task,
        user=request.user,
        comment=comment_text,
    )

    messages.success(
        request,
        "Your comment was added successfully.",
    )

    return redirect(
        "task_detail",
        task_id=task.pk,
    )


# ============================================================
# EDIT TASK
# ============================================================

@manager_required
def task_edit(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related(
            "project",
            "created_by",
            "assigned_to",
        ),
        pk=task_id,
    )

    user = request.user

    if not can_manage_task(user, task):
        return HttpResponseForbidden(
            "You do not have permission "
            "to edit this task."
        )

    if request.method == "POST":
        old_assigned_to_id = task.assigned_to_id

        form = TaskForm(
            request.POST,
            instance=task,
            user=user,
        )

        if form.is_valid():
            updated_task = form.save(commit=False)

            if not can_manage_project(
                user,
                updated_task.project,
            ):
                return HttpResponseForbidden(
                    "You cannot move this task "
                    "to the selected project."
                )

            if (
                updated_task.assigned_to_id
                and not updated_task.project.members.filter(
                    pk=updated_task.assigned_to_id
                ).exists()
            ):
                form.add_error(
                    "assigned_to",
                    "The assigned employee must be "
                    "a member of the selected project.",
                )

            else:
                with transaction.atomic():
                    # Serialize edits and submission creation.
                    locked_task = get_object_or_404(
                        Task.objects.select_for_update(),
                        pk=task.pk,
                    )

                    submission_state, latest_submission = (
                        get_submission_state(locked_task)
                    )

                    if submission_state in (
                        "pending",
                        "approved",
                    ):
                        protected_fields_changed = (
                            updated_task.project_id
                            != locked_task.project_id
                            or updated_task.assigned_to_id
                            != locked_task.assigned_to_id
                            or updated_task.status
                            != locked_task.status
                        )

                        if protected_fields_changed:
                            messages.error(
                                request,
                                "Project, assignee and task status "
                                "cannot be changed while work "
                                "is pending review or approved.",
                            )
                            return redirect(
                                "task_edit",
                                task_id=task.pk,
                            )

                    updated_task.save()
                    form.save_m2m()

                    new_assigned_to_id = (
                        updated_task.assigned_to_id
                    )

                    if (
                        new_assigned_to_id
                        and new_assigned_to_id
                        != old_assigned_to_id
                        and new_assigned_to_id != user.pk
                    ):
                        creator_name = (
                            user.get_full_name()
                            or user.username
                        )

                        notify_user(
                            recipient=updated_task.assigned_to,
                            title="Task Assigned to You",
                            message=(
                                "You have been assigned "
                                f'the task "{updated_task.title}" '
                                f"by {creator_name}."
                            ),
                            notification_type="task_assigned",
                            task=updated_task,
                        )

                messages.success(
                    request,
                    f'Task "{updated_task.title}" '
                    "was updated successfully.",
                )

                return redirect(
                    "task_detail",
                    task_id=updated_task.pk,
                )

    else:
        form = TaskForm(
            instance=task,
            user=user,
        )

    return render(
        request,
        "tasks/task_form.html",
        {
            "form": form,
            "task": task,
            "page_title": "Edit Task",
            "button_text": "Save Changes",
        },
    )


# ============================================================
# DELETE TASK
# ============================================================

@manager_required
def task_delete(request, task_id):
    task = get_object_or_404(
        Task.objects.select_related(
            "project",
            "created_by",
        ),
        pk=task_id,
    )

    if not can_manage_task(request.user, task):
        return HttpResponseForbidden(
            "You do not have permission "
            "to delete this task."
        )

    if request.method == "POST":
        task_title = task.title
        task.delete()

        messages.success(
            request,
            f'Task "{task_title}" '
            "was deleted successfully.",
        )

        return redirect("task_list")

    return render(
        request,
        "tasks/task_confirm_delete.html",
        {
            "task": task,
        },
    )
