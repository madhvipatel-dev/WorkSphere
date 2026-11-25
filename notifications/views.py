
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    """
    Display notifications for the currently logged-in user.
    """

    notifications = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related(
            "related_task",
            "related_project",
            "related_meeting",
        )
    )

    unread_count = notifications.filter(
        is_read=False
    ).count()

    total_count = notifications.count()

    read_count = total_count - unread_count

    context = {
        "notifications": notifications,
        "unread_count": unread_count,
        "read_count": read_count,
        "total_count": total_count,
    }

    return render(
        request,
        "notifications/notification_list.html",
        context,
    )


@login_required
def mark_notification_read(request, notification_id):
    """
    Mark a single notification as read and
    redirect to its related object.
    """

    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user,
    )

    if not notification.is_read:
        notification.is_read = True
        notification.save(
            update_fields=["is_read"]
        )

    # Open related task.
    if notification.related_task_id:
        return redirect(
            "task_detail",
            task_id=notification.related_task_id,
        )

    # Open related project.
    if notification.related_project_id:
        return redirect(
            "project_detail",
            notification.related_project_id,
        )

    # Open related meeting.
    if notification.related_meeting_id:
        return redirect(
            "meeting_detail",
            notification.related_meeting_id,
        )

    return redirect("notification_list")


@login_required
@require_POST
def mark_all_notifications_read(request):
    """
    Mark all unread notifications as read.
    """

    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(
        is_read=True
    )

    messages.success(
        request,
        "All notifications have been marked as read.",
    )

    return redirect("notification_list")
