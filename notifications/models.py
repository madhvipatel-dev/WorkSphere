
from django.conf import settings
from django.db import models


class Notification(models.Model):

    TYPE_CHOICES = [
        ("task_assigned", "Task Assigned"),
        ("work_submitted", "Work Submitted"),
        ("work_approved", "Work Approved"),
        ("work_rejected", "Work Rejected"),
        ("changes_requested", "Changes Requested"),
        ("comment", "Task Comment"),
        ("meeting", "Meeting"),
        ("project", "Project"),
        ("deadline", "Deadline Reminder"),
        ("system", "System"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    title = models.CharField(max_length=200)

    message = models.TextField()

    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        default="system",
    )

    is_read = models.BooleanField(default=False)

    related_task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    related_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    related_meeting = models.ForeignKey(
        "meetings.Meeting",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.recipient.username} - "
            f"{self.title}"
        )
