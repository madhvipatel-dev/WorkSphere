
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, OuterRef


class Project(models.Model):

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("on_hold", "On Hold"),
    ]

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    start_date = models.DateField(
        null=True,
        blank=True
    )

    deadline = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="planning"
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_projects"
    )

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="projects"
    )

    # Client assigned to this project.
    # Existing projects remain valid without a client.
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_projects",
        limit_choices_to={
            "profile__role": "client",
        },
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        if self.client_id:
            profile = getattr(self.client, "profile", None)

            if (
                profile is None
                or profile.role != "client"
                or not profile.is_approved
                or not self.client.is_active
            ):
                raise ValidationError({
                    "client": (
                        "Select an active, approved user "
                        "with the Client role."
                    )
                })

    # ========================================================
    # TASK STATISTICS
    # ========================================================

    @property
    def total_tasks(self):
        """
        Total tasks belonging to this project.
        """
        return self.tasks.count()

    @property
    def completed_tasks(self):
        """
        Tasks marked Completed by employees.

        This is a work-status count, not an approval count.
        """
        return self.tasks.filter(
            status="completed"
        ).count()

    @property
    def pending_review_tasks(self):
        """
        Count tasks whose latest submission is pending review.

        A task is counted once, even if it has
        multiple historical submissions.
        """
        from tasks.models import TaskSubmission

        latest_submission = (
            TaskSubmission.objects.filter(
                task_id=OuterRef("pk")
            )
            .order_by("-submitted_at", "-pk")
            .values("status")[:1]
        )

        return (
            self.tasks.annotate(
                latest_review_status=models.Subquery(
                    latest_submission
                )
            )
            .filter(
                latest_review_status="pending"
            )
            .count()
        )

    @property
    def approved_tasks(self):
        """
        Count tasks with an approved latest submission.

        Approval must be the current submission decision,
        rather than an older historical decision.
        """
        from tasks.models import TaskSubmission

        latest_submission = (
            TaskSubmission.objects.filter(
                task_id=OuterRef("pk")
            )
            .order_by("-submitted_at", "-pk")
            .values("status")[:1]
        )

        return (
            self.tasks.annotate(
                latest_review_status=models.Subquery(
                    latest_submission
                )
            )
            .filter(
                latest_review_status="approved",
                status="completed",
            )
            .count()
        )

    @property
    def rejected_tasks(self):
        """
        Count tasks whose latest submission was rejected.
        """
        from tasks.models import TaskSubmission

        latest_submission = (
            TaskSubmission.objects.filter(
                task_id=OuterRef("pk")
            )
            .order_by("-submitted_at", "-pk")
            .values("status")[:1]
        )

        return (
            self.tasks.annotate(
                latest_review_status=models.Subquery(
                    latest_submission
                )
            )
            .filter(
                latest_review_status="rejected"
            )
            .count()
        )

    @property
    def changes_requested_tasks(self):
        """
        Count tasks whose latest submission
        requires changes.
        """
        from tasks.models import TaskSubmission

        latest_submission = (
            TaskSubmission.objects.filter(
                task_id=OuterRef("pk")
            )
            .order_by("-submitted_at", "-pk")
            .values("status")[:1]
        )

        return (
            self.tasks.annotate(
                latest_review_status=models.Subquery(
                    latest_submission
                )
            )
            .filter(
                latest_review_status="changes_requested"
            )
            .count()
        )

    # ========================================================
    # PROJECT PROGRESS
    # ========================================================

    @property
    def progress_percentage(self):
        """
        Verified project progress.

        Only completed tasks whose latest submission
        is approved contribute to this percentage.

        Formula:
            approved_tasks / total_tasks * 100
        """
        total = self.total_tasks

        if total == 0:
            return 0

        return round(
            (self.approved_tasks / total) * 100
        )

    @property
    def employee_completion_percentage(self):
        """
        Employee-reported completion percentage.

        This may be higher than verified project progress
        when work is still awaiting manager review.
        """
        total = self.total_tasks

        if total == 0:
            return 0

        return round(
            (self.completed_tasks / total) * 100
        )

    @property
    def remaining_tasks(self):
        """
        Tasks not yet approved.

        Includes tasks that are incomplete, pending review,
        rejected or awaiting changes.
        """
        return max(
            self.total_tasks - self.approved_tasks,
            0
        )
