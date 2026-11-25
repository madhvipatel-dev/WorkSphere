
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import AuditLog


def can_view_audit_logs(user):
    """
    Only active WorkSphere administrators
    may access the audit history.
    """

    if not user.is_authenticated or not user.is_active:
        return False

    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)

    return bool(
        profile
        and profile.is_approved
        and profile.role == "admin"
    )


@login_required
@require_GET
def audit_log_list(request):
    """
    Read-only audit log dashboard.

    Supports:
    - Search
    - Action filtering
    - HTTP status filtering
    - Pagination
    """

    if not can_view_audit_logs(request.user):
        raise PermissionDenied(
            "Only WorkSphere administrators "
            "can view audit logs."
        )

    logs = AuditLog.objects.select_related(
        "user"
    ).order_by(
        "-created_at",
        "-pk",
    )

    search_query = request.GET.get(
        "search", ""
    ).strip()[:200]

    action_filter = request.GET.get(
        "action", ""
    ).strip()[:100]

    status_filter = request.GET.get(
        "status", ""
    ).strip()

    if search_query:
        logs = logs.filter(
            Q(user__username__icontains=search_query)
            | Q(action__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(request_path__icontains=search_query)
            | Q(ip_address__icontains=search_query)
        )

    if action_filter:
        logs = logs.filter(
            action=action_filter
        )

    if status_filter:
        if status_filter.isdigit():
            logs = logs.filter(
                status_code=int(status_filter)
            )

    total_logs = AuditLog.objects.count()

    successful_logs = AuditLog.objects.filter(
        status_code__gte=200,
        status_code__lt=400,
    ).count()

    client_error_logs = AuditLog.objects.filter(
        status_code__gte=400,
        status_code__lt=500,
    ).count()

    server_error_logs = AuditLog.objects.filter(
        status_code__gte=500,
    ).count()

    available_actions = (
        AuditLog.objects.order_by("action")
        .values_list("action", flat=True)
        .distinct()
    )

    paginator = Paginator(logs, 25)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "ws_audit/audit_log_list.html",
        {
            "logs": page_obj,
            "page_obj": page_obj,
            "total_logs": total_logs,
            "successful_logs": successful_logs,
            "client_error_logs": client_error_logs,
            "server_error_logs": server_error_logs,
            "available_actions": available_actions,
            "search_query": search_query,
            "action_filter": action_filter,
            "status_filter": status_filter,
        },
    )
