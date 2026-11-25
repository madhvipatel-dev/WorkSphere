
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from notifications.models import Notification

from .models import TaskSubmission


def get_user_role(user):
    """
    Return the user's approved WorkSphere role.

    Django staff status alone does not grant WorkSphere Admin access.
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


def is_admin(user):
    return get_user_role(user) == "admin"


def is_manager(user):
    return get_user_role(user) == "manager"


def can_review_submission(user, submission):
    """
    Superusers can review all submissions.

    WorkSphere Admins and Managers can review submissions
    belonging to projects they own.
    """
    role = get_user_role(user)

    if role not in ("admin", "manager"):
        return False

    if user.is_superuser:
        return True

    return submission.task.project.owner_id == user.pk


def get_authorized_submissions(user):
    """
    Return only submissions visible to the authorized reviewer.
    """
    submissions = TaskSubmission.objects.select_related(
        "task",
        "task__project",
        "submitted_by",
    )

    role = get_user_role(user)

    if role not in ("admin", "manager"):
        return submissions.none()

    if user.is_superuser:
        return submissions

    return submissions.filter(
        task__project__owner=user
    )


def require_reviewer(user):
    """
    Prevent Employees, Clients, inactive users, and
    unapproved accounts from accessing review pages.
    """
    if get_user_role(user) not in ("admin", "manager"):
        raise PermissionDenied(
            "Only authorized WorkSphere Admins and Managers "
            "can review submitted work."
        )


@login_required
def manager_submissions(request):
    """
    Display submissions belonging to projects
    the current reviewer is authorized to manage.
    """
    require_reviewer(request.user)

    submissions = get_authorized_submissions(request.user)

    status_filter = request.GET.get("status", "").strip()
    search_query = request.GET.get("search", "").strip()

    valid_statuses = {
        choice[0]
        for choice in TaskSubmission.STATUS_CHOICES
    }

    if status_filter in valid_statuses:
        submissions = submissions.filter(
            status=status_filter
        )

    if search_query:
        submissions = submissions.filter(
            Q(task__title__icontains=search_query)
            | Q(submitted_by__username__icontains=search_query)
            | Q(submitted_by__first_name__icontains=search_query)
            | Q(submitted_by__last_name__icontains=search_query)
            | Q(task__project__name__icontains=search_query)
        )

    context = {
        "submissions": submissions.order_by("-submitted_at"),
        "status_filter": status_filter,
        "search_query": search_query,
        "status_choices": TaskSubmission.STATUS_CHOICES,
    }

    return render(
        request,
        "tasks/manager_submissions.html",
        context,
    )


@login_required
@require_http_methods(["GET", "POST"])
def review_submission(request, submission_id):
    """
    Review an employee's pending work submission.

    Only pending submissions can receive a decision.
    Once reviewed, the submission history remains unchanged.
    """
    require_reviewer(request.user)

    submission = get_object_or_404(
        get_authorized_submissions(request.user),
        pk=submission_id,
    )

    if not can_review_submission(request.user, submission):
        raise PermissionDenied(
            "You cannot review submissions from this project."
        )

    if request.method == "GET":
        return render(
            request,
            "tasks/review_submission.html",
            {
                "submission": submission,
            },
        )

    action = request.POST.get("action", "").strip()
    feedback = request.POST.get(
        "manager_feedback", ""
    ).strip()

    valid_actions = {
        "approved": {
            "title": "Work Approved",
            "notification_type": "work_approved",
            "action_text": "approved",
        },
        "rejected": {
            "title": "Work Rejected",
            "notification_type": "work_rejected",
            "action_text": "rejected",
        },
        "changes_requested": {
            "title": "Changes Requested",
            "notification_type": "changes_requested",
            "action_text": "requested changes to",
        },
    }

    if action not in valid_actions:
        messages.error(
            request,
            "Please select a valid review action."
        )
        return redirect(
            "review_submission",
            submission_id=submission_id,
        )

    if action in ("rejected", "changes_requested") and not feedback:
        messages.error(
            request,
            "Feedback is required when rejecting work "
            "or requesting changes."
        )
        return redirect(
            "review_submission",
            submission_id=submission_id,
        )

    with transaction.atomic():
        submission = get_object_or_404(
            get_authorized_submissions(
                request.user
            ).select_for_update(),
            pk=submission_id,
        )

        if not can_review_submission(request.user, submission):
            raise PermissionDenied(
                "You cannot review submissions from this project."
            )

        if submission.status != "pending":
            messages.warning(
                request,
                "This submission has already been reviewed. "
                "Its previous decision cannot be changed."
            )
            return redirect("manager_submissions")

        submission.status = action
        submission.manager_feedback = feedback
        submission.reviewed_at = timezone.now()

        submission.save(
            update_fields=[
                "status",
                "manager_feedback",
                "reviewed_at",
            ]
        )

        notification_details = valid_actions[action]

        reviewer_name = (
            request.user.get_full_name()
            or request.user.username
        )

        notification_message = (
            f'{reviewer_name} '
            f'{notification_details["action_text"]} '
            f'your submitted work for the task '
            f'"{submission.task.title}".'
        )

        if feedback:
            notification_message += f" Feedback: {feedback}"

        Notification.objects.create(
            recipient=submission.submitted_by,
            title=notification_details["title"],
            message=notification_message,
            notification_type=notification_details[
                "notification_type"
            ],
            related_task=submission.task,
        )

    messages.success(
        request,
        f'Submission for "{submission.task.title}" '
        f'was marked as {submission.get_status_display()}.'
    )

    return redirect("manager_submissions")
