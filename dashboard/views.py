
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render

from accounts.permissions import ROLE_LABELS
from meetings.models import Meeting
from projects.models import Project
from tasks.models import Task
from notifications.models import Notification


# =========================================================
# ROLE HELPER
# =========================================================

def get_user_role(user):
    """
    Return the approved WorkSphere role.

    Superusers are WorkSphere Admins.

    Django is_staff alone does NOT grant
    WorkSphere Admin permissions.

    Inactive, unapproved, and invalid-role
    users receive no WorkSphere role.
    """

    if not user or not user.is_authenticated:
        return None

    if not user.is_active:
        return None

    if user.is_superuser:
        return "admin"

    profile = getattr(user, "profile", None)

    if profile is None:
        return None

    if not profile.is_approved:
        return None

    role = str(
        profile.role or ""
    ).strip().lower()

    valid_roles = {
        "admin",
        "manager",
        "employee",
        "client",
    }

    if role not in valid_roles:
        return None

    return role


# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard_home(request):

    user = request.user

    role_key = get_user_role(user)

    # -----------------------------------------------------
    # DENY INVALID OR UNAPPROVED USERS
    # -----------------------------------------------------

    if role_key is None:

        raise PermissionDenied(
            "Your WorkSphere account is not "
            "approved or does not have a valid role."
        )

    # -----------------------------------------------------
    # CLIENT DASHBOARD REDIRECT
    # -----------------------------------------------------

    if role_key == "client":

        return redirect(
            "/dashboard/client/"
        )

    # -----------------------------------------------------
    # ROLE LABEL
    # -----------------------------------------------------

    role_labels = {
        str(key).strip().lower(): value
        for key, value in ROLE_LABELS.items()
    }

    role = role_labels.get(
        role_key,
        role_key.title(),
    )

    # =====================================================
    # ADMIN DASHBOARD
    # =====================================================

    if role_key == "admin":

        projects = Project.objects.all()

        tasks = Task.objects.all()

        meetings = Meeting.objects.all()

        total_projects = projects.count()

        total_tasks = tasks.count()

        total_meetings = meetings.count()

        completed_tasks = tasks.filter(
            status="completed"
        ).count()

        pending_tasks = tasks.exclude(
            status="completed"
        ).count()

        active_projects = projects.filter(
            status="in_progress"
        ).count()

        upcoming_meetings = meetings.filter(
            status="scheduled"
        ).count()

        recent_projects = projects.order_by(
            "-id"
        )[:5]

        context = {
            "role": role,
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "total_meetings": total_meetings,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "active_projects": active_projects,
            "upcoming_meetings": upcoming_meetings,
        }

    # =====================================================
    # MANAGER DASHBOARD
    # =====================================================

    elif role_key == "manager":

        # Managers can see projects they own
        # or projects where they are members.

        manager_projects = Project.objects.filter(
            Q(owner=user)
            | Q(members=user)
        ).distinct()

        manager_tasks = Task.objects.filter(
            project__in=manager_projects
        ).distinct()

        # Restrict meeting visibility to projects
        # the manager can currently access.

        manager_meetings = Meeting.objects.filter(
            project__in=manager_projects
        ).distinct()

        total_projects = manager_projects.count()

        total_tasks = manager_tasks.count()

        total_meetings = manager_meetings.count()

        completed_tasks = manager_tasks.filter(
            status="completed"
        ).count()

        pending_tasks = manager_tasks.exclude(
            status="completed"
        ).count()

        active_projects = manager_projects.filter(
            status="in_progress"
        ).count()

        upcoming_meetings = manager_meetings.filter(
            status="scheduled"
        ).count()

        recent_projects = manager_projects.order_by(
            "-id"
        )[:5]

        context = {
            "role": role,
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "total_meetings": total_meetings,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "active_projects": active_projects,
            "upcoming_meetings": upcoming_meetings,
        }

    # =====================================================
    # EMPLOYEE DASHBOARD
    # =====================================================

    elif role_key == "employee":

        projects = Project.objects.filter(
            members=user
        ).distinct()

        # Count tasks assigned directly to
        # the employee on accessible projects.

        my_tasks = Task.objects.filter(
            assigned_to=user,
            project__in=projects,
        ).distinct()

        # Employees see meetings belonging
        # to their current assigned projects.

        meetings = Meeting.objects.filter(
            project__in=projects
        ).distinct()

        total_projects = projects.count()

        total_tasks = my_tasks.count()

        total_meetings = meetings.count()

        completed_tasks = my_tasks.filter(
            status="completed"
        ).count()

        pending_tasks = my_tasks.exclude(
            status="completed"
        ).count()

        upcoming_meetings = meetings.filter(
            status="scheduled"
        ).count()

        recent_projects = projects.order_by(
            "-id"
        )[:5]

        context = {
            "role": role,
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "total_meetings": total_meetings,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "upcoming_meetings": upcoming_meetings,
        }

    else:

        raise PermissionDenied(
            "You do not have permission "
            "to access this dashboard."
        )

    # =====================================================
    # SHARED DASHBOARD DATA
    # =====================================================

    context["recent_projects"] = recent_projects

    context["recent_notifications"] = (
        Notification.objects.filter(
            recipient=user
        )
        .select_related(
            "related_task"
        )
        .order_by(
            "-created_at"
        )[:5]
    )

    context["unread_notifications_count"] = (
        Notification.objects.filter(
            recipient=user,
            is_read=False,
        ).count()
    )

    context["user_role"] = role_key

    # =====================================================
    # RENDER DASHBOARD
    # =====================================================

    return render(
        request,
        "dashboard/dashboard.html",
        context,
    )
